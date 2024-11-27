import os
import json
import logging
from decimal import Decimal
from datetime import date, datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


class CustomerAnalyzer:
    def __init__(self, temperature=None):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4')
        self.temperature = temperature if temperature is not None else float(os.getenv('TEMPERATURE', 0.7))
        self.system_prompt = """You are a Gatekeeper contract management software expert. Analyze customer usage data with precise interpretation of key features:
        0. Overview
        - Focus on key metrics and risks and provide a short paragraphph summary of the analysis.
        - Include positive and negative trends, areas of improvement, and actionable recommendations in a positive tone.
        - ALWAYS start the Overview paragraph with the customer name.
        
        1. Document Management & Compliance
        - Master Record coverage analysis
          * These are finalized, executed agreements serving as authoritative versions
          * Calculate % of contracts with master records
          * Assess AI summary enablement and utilization
          * Flag contracts missing master records as compliance risks

        2. Ownership & Accountability
        - Contract owner assignment analysis
          * Owners are Subject Matter Experts and key points of contact
          * Calculate % of contracts with assigned owners
          * Identify gaps in ownership assignment
          * Impact on contract visibility and management

        3. Task Management & Events
        - Event metrics analysis
          * Events are task management tools with due dates, owners, and approvers
          * Calculate completion rates and average response times
          * Assess overdue events and their impact
          * Evaluate recurring event usage

        4. Feature Adoption with focus on E-Signatures
        - E-signature solution analysis:
          * If DocuSign is "Disabled" but GK E-signs are being used, this indicates customer preference for Gatekeeper's native e-signature solution
          * If DocuSign is "Enabled", compare usage between DocuSign and GK E-signs to understand preferred platform
          * Calculate total e-signatures across both platforms
          * Identify if customer is effectively utilizing their chosen e-signature solution(s)
        - Smart Forms implementation
        - RBAC configuration
        - Custom views and filters usage
        - Auto-build feature adoption

        5. Risk Assessment
        - Identify specific risks based on:
          * Missing master records
          * Unassigned contract owners
          * Overdue events
          * Low feature adoption rates

        6. Actionable Recommendations
        - Prioritized list of actions based on:
          * Compliance risks
          * Process inefficiencies
          * Feature underutilization
          * User adoption challenges
          * E-signature strategy optimization

        Focus on actual metrics and their business impact -*** YOU NEED TO BE CONSISTENT IN YOUR RESPONSES IF YOU ARE SENT THE SAME DATASET I EXPECT THE SAME RESPONSE.*** When analyzing e-signatures, remember that "DocuSign Disabled" is not a negative if the customer is actively using Gatekeeper's e-signature solution. Provide specific, data-driven insights. ****
        YOU MUST ALWAYS REPLY IN A FRIENDLY POSITIVE WAY ****"""

    def analyze_customer(self, customer_data):
        try:
            data_str = json.dumps(customer_data, indent=2, cls=CustomJSONEncoder)
            logging.debug(f"Preparing analysis for customer: {customer_data.get('customer')}")

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user",
                 "content": f"Analyze this customer's usage data focusing on key metrics and risks:\n{data_str}"}
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=4000
            )

            analysis_result = {
                "customer_name": customer_data.get('customer'),
                "analysis": response.choices[0].message.content,
                "usage_tokens": response.usage.total_tokens,
                "raw_data": customer_data
            }

            logging.debug(f"Analysis completed for customer: {customer_data.get('customer')}")
            return analysis_result

        except Exception as e:
            logging.error(f"OpenAI API error for customer {customer_data.get('customer')}: {e}")
            raise