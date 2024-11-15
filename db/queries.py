def fetch_live_customers(conn):
    """
    Fetches the list of live customers with their details.

    :param conn: Database connection object
    :return: List of tuples containing customer details
    """
    query = """
    SELECT t.company AS customer, t.id AS tenant_id, 
        CASE WHEN tp.plan = 0 THEN 'Starter' 
            WHEN tp.plan = 1 THEN 'Pro' 
            WHEN tp.plan = 2 THEN 'Enterprise' 
            WHEN tp.plan = 3 THEN 'Custom' 
            ELSE 'Contract Now' 
        END AS plan, 
        iss.schema_name,
        tp.hubspot_id 
    FROM public.tenants t 
    LEFT JOIN public.tenant_profiles tp ON t.id = tp.tenant_id 
    LEFT JOIN information_schema.schemata iss ON t.id::varchar(255) = reverse(split_part(reverse(iss.schema_name), '_', 1)) 
    WHERE tp.status = 1 
      AND iss.schema_name IS NOT NULL
    """
    with conn.cursor() as cursor:
        cursor.execute(query)
        results = cursor.fetchall()
    return results

def fetch_customer_additional_data(conn, tenant_id, schema_name, months_lookback=1):
    query = f"""
    WITH settings_check AS (
        SELECT
            (SELECT CASE WHEN COALESCE(esign, false) THEN 'Enabled' ELSE 'Disabled' END
             FROM {schema_name}.settings LIMIT 1) as gk_esign_enabled,
            COALESCE(
                (SELECT CASE
                    WHEN p.jsonb_value <> '{{}}'::jsonb THEN 'Enabled'
                    ELSE 'Disabled'
                END
                FROM {schema_name}.properties p
                WHERE p.scope_name = 'docu_sign' AND p.name = 'user_info'),
                'Disabled'
            ) as docusign_enabled
    ),

    logged_in_users AS (
        SELECT COUNT(DISTINCT u.id) as logged_in_count
        FROM public.users u
        LEFT JOIN public.employments e ON e.user_id = u.id
        WHERE e.tenant_id = {tenant_id}
        AND u.current_sign_in_at >= CURRENT_DATE - INTERVAL '{months_lookback} months'
        AND u.email NOT LIKE '%%@gatekeeperhq.com'
    ),
    active_users AS (
        SELECT COUNT(DISTINCT v.whodunnit::integer) as active_count
        FROM {schema_name}.versions v
        JOIN public.users u ON u.id = v.whodunnit::integer
        WHERE v.created_at >= CURRENT_DATE - INTERVAL '{months_lookback} months'
        AND u.email NOT LIKE '%%@gatekeeperhq.com'
    ),
    inactive_users AS (
        SELECT (logged_in_count - active_count) as inactive_count
        FROM logged_in_users, active_users
    ),
    settings_rbac_check AS (
        SELECT CASE WHEN access_groups = true THEN 'Enabled' ELSE 'Disabled' END as "RBAC Status"
        FROM {schema_name}.settings
    ),
    group_counts AS (
        SELECT COUNT(CASE WHEN kind = 10 THEN 1 END) as "RBAC Groups"
        FROM {schema_name}.access_groups
        WHERE predefined = false
    ),

    saved_custom_views AS (
        SELECT COUNT(DISTINCT id) AS "Saved Custom Views"
        FROM {schema_name}.ui_tables_filters ui
        WHERE ui.title <> 'Default' AND ui.meta_status = '20'
    ),
    smart_forms_enabled AS (
        SELECT COALESCE(
            (SELECT CASE WHEN tf.meta_status = 10 THEN 'ON' ELSE 'OFF' END
             FROM public.tenants_features tf
             JOIN public.tenant_profiles tp ON tf.tenant_profile_id = {tenant_id}
             WHERE tf.kind = '280' AND tp.tenant_id = {tenant_id}),
            'OFF'
        ) AS "Smart Forms Enabled"
    ),

    signing_stats AS (
        SELECT
            CASE
                WHEN provider = 10 THEN 'GK E-Sign'
                WHEN provider = 20 THEN 'DocuSign'
            END as signing_provider,
            COUNT(DISTINCT esp.id) as signed_count
        FROM {schema_name}.esign_sign_processes esp
        WHERE esp.meta_status = 100
            AND esp.file_host_type = 'Contract'
            AND esp.updated_at >= CURRENT_DATE - INTERVAL '{months_lookback} months'
        GROUP BY provider
    ),

    scored_entities AS (
        SELECT
            ct.id AS tab_id,
            ct.title AS tab_name,
            cts.scorable_type,
            cts.scorable_id,
            COALESCE(
                c.title,
                s.name,
                p.title,
                'Unknown'
            ) AS entity_name,
            MAX(cts.updated_at::Date) AS latest_update
        FROM {schema_name}.custom_tabs ct
        LEFT JOIN {schema_name}.custom_tab_scores cts ON ct.id = cts.custom_tab_id
            AND cts.meta_status = 20
            AND (cts.value != 0 OR cts.value IS NULL)
        LEFT JOIN {schema_name}.contracts c ON cts.scorable_type = 'Contract' AND cts.scorable_id = c.id
        LEFT JOIN {schema_name}.suppliers s ON cts.scorable_type = 'Supplier' AND cts.scorable_id = s.id
        LEFT JOIN {schema_name}.projects p ON cts.scorable_type = 'Project' AND cts.scorable_id = p.id
        WHERE ct.scored = true
        GROUP BY
            ct.id,
            ct.title,
            cts.scorable_type,
            cts.scorable_id,
            COALESCE(c.title, s.name, p.title, 'Unknown')
    ),

    null_scores AS (
        SELECT COUNT(*) as tabs_with_null_scores
        FROM {schema_name}.custom_tabs ct
        WHERE ct.scored = true
        AND NOT EXISTS (
            SELECT 1
            FROM {schema_name}.custom_tab_scores cts
            WHERE cts.custom_tab_id = ct.id
            AND cts.value != 0
            AND cts.meta_status = 20
        )
    ),
    smart_forms_summary AS (
        SELECT
            sfe."Smart Forms Enabled" AS "Smart Forms Enabled",
            COUNT(DISTINCT se.tab_id) AS "Smart Forms Count",
            STRING_AGG(DISTINCT se.scorable_type, ' | ' ORDER BY se.scorable_type) AS "Smart Form Types",
            MAX(se.latest_update) AS "Latest Updated Score",
            COALESCE(ns.tabs_with_null_scores, 0) AS "Smart Forms with No Scores"
        FROM smart_forms_enabled sfe
        LEFT JOIN scored_entities se ON true
        CROSS JOIN null_scores ns
        GROUP BY sfe."Smart Forms Enabled", ns.tabs_with_null_scores
    ),

    autobuild_status AS (
        SELECT CASE WHEN s.supplier_auto_build = True
                    THEN 'ON'
                    ELSE 'OFF'
               END AS "Auto Build Enabled"
        FROM {schema_name}.settings s
    ),
    autobuild_count AS (
        WITH autobuild_fields AS (
            SELECT cf.id::text as field_id
            FROM {schema_name}.custom_fields cf
            JOIN {schema_name}.custom_groups cg ON cf.custom_group_id = cg.id
            WHERE cg.predefined_kind = 100
        )
        SELECT COUNT(DISTINCT s.id) AS "Autobuild Supplier Count"
        FROM {schema_name}.suppliers s
        WHERE EXISTS (
            SELECT 1
            FROM autobuild_fields af
            WHERE s.custom_fields_data ? af.field_id
            AND s.custom_fields_data->>af.field_id IS NOT NULL
            AND s.custom_fields_data->>af.field_id != ''
        )
    )

    SELECT
        logged_in_users.logged_in_count as "Total Logged In Users ({months_lookback}m)",
        active_users.active_count as "Users Who Performed Actions ({months_lookback}m)",
        inactive_users.inactive_count as "Users Who Only Logged In ({months_lookback}m)",

        settings_rbac_check."RBAC Status",
        group_counts."RBAC Groups",

        total_contracts_data."Total Contracts (inc Archived)",
        total_contracts_data."Total Live Contracts",
        total_contracts_data."NEW Live Contracts ({months_lookback}m)",
        total_contracts_data."Updated Live Contracts ({months_lookback}m)",

        total_contracts_data."Main Currency",
        total_contracts_data."Average Contract Value (Live)",

        total_contracts_data."Live Contracts with Internal Owners",
        total_contracts_data."Live Contracts with NO Internal Owners",
        total_contracts_data."Percent Contracts with Internal Owners",
        contract_links_data."Live Contracts Linked to another Contract",
        supplier_links_data."Live Suppliers Linked to another Supplier",

        master_record_data."Contracts with Master Record",
        master_record_data."Percent with Master Record",
        ai_extract_data."AI Extract - Ready for Review ({months_lookback}m)",
        total_contracts_data."OpenAI Contract Summary",

        activities_data."Total Events (All Time)",
        activities_data."New Events ({months_lookback}m)",
        activities_data."Completed Events ({months_lookback}m)",
        activities_data."Overdue Events",
        activities_data."Events Avg Completion Time ({months_lookback}m)",
        activities_data."Event Types",

        smart_forms."Smart Forms Enabled",
        smart_forms."Smart Forms Count",
        smart_forms."Smart Form Types",
        smart_forms."Latest Updated Score",
        smart_forms."Smart Forms with No Scores",
        saved_custom_views."Saved Custom Views",

        autobuild_status."Auto Build Enabled",
        autobuild_count."Autobuild Supplier Count",

        settings_check.gk_esign_enabled as "eSign Enabled",
        settings_check.docusign_enabled as "DocuSign Enabled",
        COALESCE(gk_esign.signed_count, 0) as "eSigns ({months_lookback}m)",
        COALESCE(docusign.signed_count, 0) as "DocuSigns ({months_lookback}m)"

    FROM
        (SELECT
            COUNT(DISTINCT c.id) AS "Total Contracts (inc Archived)",
            COUNT(DISTINCT CASE WHEN c.created_at >= CURRENT_DATE - INTERVAL '{months_lookback} months' THEN c.id END) 
                AS "NEW Live Contracts ({months_lookback}m)",
            COUNT(DISTINCT CASE WHEN c.updated_at >= CURRENT_DATE - INTERVAL '{months_lookback} months' THEN c.id END) 
                AS "Updated Live Contracts ({months_lookback}m)",
            COUNT(DISTINCT CASE WHEN c.meta_status = 20 THEN c.id END) AS "Total Live Contracts",
            (SELECT reporting_currency FROM {schema_name}.settings LIMIT 1) AS "Main Currency",
            (SELECT CASE WHEN open_ai_contract_summary = True THEN 'ON' ELSE 'OFF' END FROM {schema_name}.settings LIMIT 1) AS "OpenAI Contract Summary",
            COALESCE(ROUND(AVG(cs.annual_value_cents) FILTER (WHERE c.meta_status = 20) / 100), 0) AS "Average Contract Value (Live)",
            COUNT(DISTINCT CASE WHEN o.id IS NOT NULL AND c.meta_status = 20 THEN c.id END) as "Live Contracts with Internal Owners",
            COUNT(DISTINCT CASE WHEN o.id IS NULL AND c.meta_status = 20 THEN c.id END) as "Live Contracts with NO Internal Owners",
            ROUND(
                (COUNT(DISTINCT CASE WHEN o.id IS NOT NULL AND c.meta_status = 20 THEN c.id END)::decimal /
                NULLIF(COUNT(DISTINCT CASE WHEN c.meta_status = 20 THEN c.id END), 0) * 100)
            , 2) as "Percent Contracts with Internal Owners"
        FROM {schema_name}.contracts c
        LEFT JOIN {schema_name}.contract_summaries cs ON c.id = cs.contract_id
        LEFT JOIN {schema_name}.owners o ON c.id = o.host_id
            AND o.host_type = 'Contract'
            AND EXISTS (
                SELECT 1
                FROM {schema_name}.owner_kinds ok
                WHERE ok.id = o.owner_kind_id
                AND ok.predefined = true
            )
        ) AS total_contracts_data

    CROSS JOIN LATERAL
        (SELECT
            COUNT(CASE WHEN has_master_record THEN 1 END) AS "Contracts with Master Record",
            ROUND(
                (COUNT(CASE WHEN has_master_record THEN 1 END)::decimal /
                NULLIF(COUNT(*), 0) * 100), 2) AS "Percent with Master Record"
        FROM {schema_name}.contract_reviews
        ) AS master_record_data

    CROSS JOIN LATERAL
        (SELECT
            COUNT(DISTINCT id) AS "AI Extract - Ready for Review ({months_lookback}m)"
        FROM {schema_name}.attachments_file_analyses_summaries
        WHERE analyzed_at::Date < CURRENT_DATE - INTERVAL '{months_lookback} months'
          AND analyzer_job_status = 30
        ) AS ai_extract_data

    CROSS JOIN LATERAL
        (SELECT
            COUNT(DISTINCT a.id) as "Total Events (All Time)",
            COUNT(DISTINCT CASE
                WHEN a.created_at >= CURRENT_DATE - INTERVAL '{months_lookback} months'
                THEN a.id END) as "New Events ({months_lookback}m)",
            COUNT(DISTINCT CASE
                WHEN a.date_completed >= CURRENT_DATE - INTERVAL '{months_lookback} months'
                THEN a.id END) as "Completed Events ({months_lookback}m)",
            COUNT(DISTINCT CASE
                WHEN a.due_date < CURRENT_DATE
                AND a.date_completed IS NULL
                THEN a.id END) as "Overdue Events",
            COALESCE(
                ROUND(AVG(CASE
                    WHEN a.date_completed >= CURRENT_DATE - INTERVAL '{months_lookback} months'
                    THEN EXTRACT(EPOCH FROM (a.date_completed - a.created_at))/86400.0
                    END))::integer, 0) as "Events Avg Completion Time ({months_lookback}m)",
            string_agg(DISTINCT co.label, ' | ' ORDER BY co.label) as "Event Types"
        FROM {schema_name}.activities a
        LEFT JOIN {schema_name}.custom_options co ON a.activity_type = co.id
        ) AS activities_data

    CROSS JOIN LATERAL
        (SELECT
            COUNT(DISTINCT c.id) as "Live Contracts Linked to another Contract"
        FROM {schema_name}.contracts c
    INNER JOIN {schema_name}.contract_links cl
                ON c.id = cl.linked_contract_id OR c.id = cl.related_contract_id
            WHERE c.meta_status = 20
            ) AS contract_links_data

        CROSS JOIN LATERAL
            (SELECT
                COUNT(DISTINCT s.id) as "Live Suppliers Linked to another Supplier"
            FROM {schema_name}.suppliers s
            INNER JOIN {schema_name}.supplier_links sl
                ON s.id = sl.linked_supplier_id OR s.id = sl.related_supplier_id
            WHERE s.meta_status = 20
            ) AS supplier_links_data

        CROSS JOIN smart_forms_summary smart_forms
        CROSS JOIN saved_custom_views
        CROSS JOIN autobuild_status
        CROSS JOIN autobuild_count
        CROSS JOIN settings_check
        LEFT JOIN signing_stats gk_esign
            ON gk_esign.signing_provider = 'GK E-Sign'
        LEFT JOIN signing_stats docusign
            ON docusign.signing_provider = 'DocuSign'
        CROSS JOIN settings_rbac_check
        CROSS JOIN group_counts
        CROSS JOIN logged_in_users
        CROSS JOIN active_users
        CROSS JOIN inactive_users;
        """

    with conn.cursor() as cursor:
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
    return results, columns