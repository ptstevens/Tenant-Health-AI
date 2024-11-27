from fpdf import FPDF
import logging
from datetime import datetime
import matplotlib.pyplot as plt
import tempfile
import os


class ReportGenerator:
    def __init__(self, months=1):
        self.pdf = None  # Initialize in generate_report to ensure fresh instance for each report
        self.months = months

    def generate_report(self, analysis_data):
        """Generate a new report with fresh PDF instance."""
        self.pdf = FPDF()  # Create new instance for each report
        self.pdf.set_auto_page_break(auto=True, margin=15)

        if not isinstance(analysis_data, dict):
            logging.error(f"Invalid analysis_data type: {type(analysis_data)}")
            raise ValueError(f"Invalid analysis_data type: {type(analysis_data)}")

        logging.debug(f"Generating report for customer: {analysis_data.get('customer_name')}")
        logging.debug(f"Analysis data keys: {analysis_data.keys()}")

        temp_dir = tempfile.mkdtemp()
        try:
            os.makedirs('reports', exist_ok=True)

            self._add_cover_page(analysis_data.get('customer_name', 'Unknown Customer'))
            self._add_overview_page(analysis_data)

            if 'raw_data' in analysis_data:
                logging.debug("Adding charts and metrics")
                self._add_metrics_tables(analysis_data['raw_data'])
            else:
                logging.warning("No raw_data found in analysis_data")


            filename = f"reports/{analysis_data['customer_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
            self.pdf.output(filename)
            logging.debug(f"PDF generated successfully: {filename}")

            return filename

        except Exception as e:
            logging.error(f"PDF generation error for {analysis_data.get('customer_name')}: {str(e)}", exc_info=True)
            raise
        finally:
            try:
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir)
            except Exception as e:
                logging.warning(f"Failed to cleanup temp files: {e}")

    def _add_cover_page(self, customer_name):
        try:
            self.pdf.add_page()

            # Logo placement
            if os.path.exists('assets/logo.png'):
                self.pdf.image('assets/logo.png', x=5, y=5, w=60)  # Adjust size as needed

            # Professional header with gradient
            self.pdf.set_fill_color(51, 122, 183)  # Blue color
            self.pdf.rect(0, 20, 210, 20, 'F')  # Gradient background

            # Report title
            self.pdf.ln(10)  # Space after logo
            self.pdf.set_text_color(255, 255, 255)
            self.pdf.set_font('Arial', 'B', 24)
            self.pdf.cell(0, 20, 'Customer Health Analysis', ln=True, align='C')

            # Customer name
            self.pdf.ln(5)
            self.pdf.set_text_color(0, 0, 0)
            self.pdf.set_font('Arial', 'B', 20)
            self.pdf.cell(0, 10, customer_name.title(), ln=True, align='C')

            # Date
            self.pdf.ln(5)
            self.pdf.set_font('Arial', '', 12)
            self.pdf.cell(0, 10, f'Generated on: {datetime.now().strftime("%B %d, %Y")}', ln=True, align='C')
            self.pdf.cell(0, 5, f'Report covers last {self.months} month{"s" if self.months != 1 else ""}', ln=True,
                          align='C')


        except Exception as e:
            logging.error(f"Error adding cover page: {e}")


    def _add_overview_page(self, analysis_data):
        try:
            self.pdf.ln(10)
            self.pdf.set_font('Arial', 'BU', 12)
            self.pdf.cell(0, 12, 'Restore Visibility Overview', ln=True)

            if 'analysis' in analysis_data:
                analysis_text = analysis_data['analysis']
                # Extract the summary as before
                summary = analysis_text.split('1. Document Management & Compliance')[
                    0] if '1.' in analysis_text else analysis_text



                # Split the text into lines and remove the first line if it matches "0. Overview"
                summary_lines = summary.splitlines()
                if summary_lines and summary_lines[0].strip().startswith("0."):
                    summary_lines.pop(0)  # Remove the first line


                # Join the remaining lines back together
                cleaned_summary = "\n".join(summary_lines).strip()

                self.pdf.set_font('Arial', '', 9)
                self.pdf.multi_cell(0, 5, cleaned_summary)
                if 'analysis' in analysis_data:
                    logging.debug("Adding detailed analysis")
                    self._add_detailed_analysis(analysis_data['analysis'])
                else:
                    logging.warning("No analysis found in analysis_data")
            else:
                logging.warning("No analysis text found for overview page")
                self.pdf.set_font('Arial', '', 9)
                self.pdf.multi_cell(0, 5, "Analysis data not available")

        except Exception as e:
            logging.error(f"Error adding overview page: {e}")


    def _add_metrics_tables(self, raw_data):
        try:
            self.pdf.add_page()
            self.pdf.set_font('Arial', 'B', 9)
            self.pdf.set_fill_color(240, 240, 240)

            metrics_groups = {
                'User Activity': [
                    'Total Logged In Users',
                    'Users Who Performed Actions',
                    'Users Who Only Logged In'
                ],
                'Contract Management': [
                    'Total Contracts (inc Archived)',
                    'Total Live Contracts',
                    'Average Contract Value (Live)'
                ],
                'Feature Adoption': [
                    'Smart Forms Count',
                    'Saved Custom Views',
                    'RBAC Status'
                ]
            }

            for group, metrics in metrics_groups.items():
                self.pdf.set_font('Arial', 'B', 9)
                self.pdf.cell(0, 10, group, ln=True, fill=True)

                self.pdf.set_font('Arial', '', 10)
                for metric in metrics:
                    found_metric = next((k for k in raw_data.keys() if k.startswith(metric)), None)
                    if found_metric:
                        value = str(raw_data[found_metric])
                        self.pdf.cell(100, 8, found_metric, border=1)
                        self.pdf.cell(90, 8, value, border=1, ln=True)
                self.pdf.ln(5)
        except Exception as e:
            logging.error(f"Error adding metrics tables: {e}")

    def _add_detailed_analysis(self, analysis):
        try:
            self.pdf.add_page()
            self.pdf.set_font('Arial', 'B', 9)
            self.pdf.cell(0, 10, 'Detailed Analysis', ln=True)

            self.pdf.set_font('Arial', '', 9)
            for line in analysis.split('\n'):
                if line.strip():
                    if any(str(i) in line[:4] for i in range(1, 8)):
                        self.pdf.set_font('Arial', 'B', 12)
                        self.pdf.ln(5)
                        self.pdf.cell(0, 10, line, ln=True)
                        self.pdf.set_font('Arial', '', 12)
                    else:
                        if line.strip().startswith('-'):
                            self.pdf.set_x(20)
                        self.pdf.multi_cell(0, 6, line)
        except Exception as e:
            logging.error(f"Error adding detailed analysis: {e}")

    def _create_user_engagement_chart(self, data, temp_dir):
        try:
            plt.close('all')
            fig = plt.figure(figsize=(10, 5))
            ax = fig.add_subplot(111)

            # Find the correct metric names based on the months value
            total_users_key = next((k for k in data.keys() if k.startswith('Total Logged In Users')), None)
            active_users_key = next((k for k in data.keys() if k.startswith('Users Who Performed Actions')), None)
            passive_users_key = next((k for k in data.keys() if k.startswith('Users Who Only Logged In')), None)

            if not all([total_users_key, active_users_key, passive_users_key]):
                logging.warning("Missing user engagement metrics")
                return None

            # Convert values to integers, handling various formats
            def safe_convert(value):
                try:
                    if isinstance(value, (int, float)):
                        return int(value)
                    return int(str(value).replace(',', ''))
                except (ValueError, TypeError):
                    return 0

            users = [
                safe_convert(data.get(total_users_key, 0)),
                safe_convert(data.get(active_users_key, 0)),
                safe_convert(data.get(passive_users_key, 0))
            ]

            # Only create chart if we have non-zero data
            if sum(users) == 0:
                logging.warning("No user engagement data available")
                return None

            labels = ['Total Users', 'Active Users', 'Passive Users']

            bars = ax.bar(labels, users, color=['#3498db', '#2ecc71', '#e74c3c'])
            ax.set_title('User Engagement Overview')

            # Add value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height,
                        f'{int(height):,}',
                        ha='center', va='bottom')

            plt.xticks(rotation=45)
            plt.tight_layout(pad=1.5)

            path = self._save_plt_as_temp_file(fig, temp_dir)
            plt.close(fig)
            return path

        except Exception as e:
            logging.error(f"Error creating user engagement chart: {e}")
            return None

    def _create_contract_metrics_chart(self, data, temp_dir):
        try:
            plt.close('all')
            fig = plt.figure(figsize=(10, 5))
            ax = fig.add_subplot(111)

            # Find the correct metric names based on the months value
            total_contracts_key = 'Total Live Contracts'
            new_contracts_key = next((k for k in data.keys() if k.startswith('NEW Live Contracts')), None)
            updated_contracts_key = next((k for k in data.keys() if k.startswith('Updated Live Contracts')), None)

            if not all([total_contracts_key, new_contracts_key, updated_contracts_key]):
                logging.warning("Missing contract metrics")
                return None

            def safe_convert(value):
                try:
                    if isinstance(value, (int, float)):
                        return int(value)
                    return int(str(value).replace(',', ''))
                except (ValueError, TypeError):
                    return 0

            values = [
                safe_convert(data.get(total_contracts_key, 0)),
                safe_convert(data.get(new_contracts_key, 0)),
                safe_convert(data.get(updated_contracts_key, 0))
            ]

            # Only create chart if we have non-zero data
            if sum(values) == 0:
                logging.warning("No contract metrics data available")
                return None

            labels = ['Total Live', 'New', 'Updated']

            bars = ax.bar(labels, values, color=['#3498db', '#2ecc71', '#f1c40f'])
            ax.set_title('Contract Activity')

            # Add value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height,
                        f'{int(height):,}',
                        ha='center', va='bottom')

            plt.xticks(rotation=45)
            plt.tight_layout(pad=1.5)

            path = self._save_plt_as_temp_file(fig, temp_dir)
            plt.close(fig)
            return path

        except Exception as e:
            logging.error(f"Error creating contract metrics chart: {e}")
            return None

    def _save_plt_as_temp_file(self, fig, temp_dir):
        try:
            temp_path = os.path.join(temp_dir, f'chart_{datetime.now().strftime("%H%M%S%f")}.png')
            fig.savefig(temp_path, format='png', bbox_inches='tight', dpi=300)
            plt.close(fig)
            return temp_path
        except Exception as e:
            logging.error(f"Error saving plot: {e}")
            return None