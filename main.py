import argparse
import csv
import logging
import os
from datetime import datetime
from ai.analyzer import CustomerAnalyzer
from db.connection import get_db_connection
from db.queries import fetch_live_customers, fetch_customer_additional_data
from report.generator import ReportGenerator


def setup_custom_logging(log_level):
    """Setup logging with custom level"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')

    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )


def process_customer(conn, customer, region, months):
    """Process a single customer's data."""
    customer_dict = {
        'customer': customer[0],
        'tenant_id': customer[1],
        'plan': customer[2],
        'schema_name': customer[3],
        'hubspot_id': customer[4],
        'region': region
    }

    try:
        additional_data, additional_columns = fetch_customer_additional_data(
            conn, customer[1], customer[3], months
        )

        if additional_data:
            row_data = additional_data[0]
            additional_dict = dict(zip(additional_columns, row_data))
            customer_dict.update(additional_dict)
            logging.info(f"Successfully processed customer: {customer[0]}")
        else:
            logging.warning(f"No additional data found for customer: {customer[0]}")

    except Exception as e:
        logging.error(f"Error processing customer {customer[0]}: {e}")
        raise

    return customer_dict


def process_region(region, test_mode=False, temperature=None, months=1):
    """Process customers for a specific region."""
    logging.info(f"Starting process for region: {region}")
    conn = None
    analyzer = CustomerAnalyzer(temperature)
    report_gen = ReportGenerator(months)

    try:
        conn = get_db_connection(region)
        customers = fetch_live_customers(conn)

        if test_mode:
            logging.info("Test mode - processing first customer only")
            customers = customers[:1]

        for customer in customers:
            try:
                customer_data = process_customer(conn, customer, region, months)
                logging.debug(f"Processed customer data keys: {customer_data.keys()}")

                # Write raw data to CSV
                raw_filename = f"raw_data/{customer_data['customer'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
                os.makedirs('raw_data', exist_ok=True)

                with open(raw_filename, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=customer_data.keys())
                    writer.writeheader()
                    writer.writerow(customer_data)

                analysis = analyzer.analyze_customer(customer_data)
                logging.debug(f"Analysis result keys: {analysis.keys() if analysis else 'No analysis generated'}")

                report_file = report_gen.generate_report(analysis)
                logging.info(f"Generated report: {report_file}")
                logging.info(f"Raw data saved to: {raw_filename}")

            except Exception as e:
                logging.error(f"Error processing customer {customer[0]}: {str(e)}")
                continue

    finally:
        if conn:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description='Process customer data with optional test mode')
    parser.add_argument('--test', action='store_true', help='Run in test mode (process only first customer)')
    parser.add_argument('--region', choices=['Staging', 'APAC', 'EU', 'US', 'CA'],
                        help='Process specific region only')
    parser.add_argument('--temperature', type=float, help='OpenAI temperature (0-1)')
    parser.add_argument('--months', type=int, default=1,
                        help='Number of months to look back for time-based metrics')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='INFO', help='Set the logging level')
    args = parser.parse_args()

    setup_custom_logging(args.log_level)

    try:
        regions = [args.region] if args.region else ['Staging', 'APAC', 'EU', 'US', 'CA']

        for region in regions:
            process_region(region, args.test, args.temperature, args.months)
            if args.test:
                break

    except Exception as e:
        logging.error(f"Error in main process: {e}")
        raise


if __name__ == "__main__":
    main()