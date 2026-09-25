#!/usr/bin/env python3
"""
Generate Skill Compliance Report with Industry Standards
Parses skill-validator, skill-spector, benchmark.md, and evals.json
Outputs comprehensive HTML report with improved organization
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


EXAMPLE_PROMPTS_DIR = "example-prompts"


class SkillComplianceReportGenerator:
    def __init__(self, skills_root: Path, validator_json: Optional[str] = None, spector_json: Optional[str] = None,
                 skills_config_path: Optional[str] = None, bandit_json: Optional[str] = None,
                 zizmor_json: Optional[str] = None, scorecard_json: Optional[str] = None):
        self.skills_root = skills_root
        self.skills_data = {}
        self.validator_data = {}
        self.spector_data = {}
        self.bandit_data = {}
        self.bandit_repo_totals = None
        self.zizmor_data = None
        self.scorecard_data = None
        self.skills_config = {}
        self.skills_prompts_url = {}
        self.github_run_id = os.getenv('GITHUB_RUN_ID', '')
        self.github_repo = os.getenv('GITHUB_REPOSITORY', '')
        self.components = defaultdict(lambda: {
            'product': '',
            'skills': [],
            'total_eval_tests': 0,
            'eval_metrics': {},
            'validator_findings': {},
            'spector_scores': [],
            'total_loc': 0
        })
        
        # Load skills-config.json for component mapping
        if skills_config_path and Path(skills_config_path).exists():
            self.load_skills_config(skills_config_path)
        
        # Load validator and spector data if available
        if validator_json and Path(validator_json).exists():
            self.load_validator_data(validator_json)
        if spector_json and Path(spector_json).exists():
            self.load_spector_data(spector_json)
        if bandit_json and Path(bandit_json).exists():
            self.load_bandit_data(bandit_json)
        if zizmor_json and Path(zizmor_json).exists():
            self.load_zizmor_data(zizmor_json)
        if scorecard_json and Path(scorecard_json).exists():
            self.load_scorecard_data(scorecard_json)

    def load_skills_config(self, config_path: str) -> None:
        """Load skills configuration mapping skills to components"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            # Build a mapping of skill name to product/component
            for product_entry in config.get('products', []):
                product_name = product_entry.get('product', '')
                product_ref = product_entry.get('ref', 'main')
                for skill in product_entry.get('skills', []):
                    skill_name = skill.get('name', '')
                    if skill_name:
                        self.skills_config[skill_name] = product_name
                        ref = os.getenv("GITHUB_REF_NAME") or "main"
                        has_prompts = (self.skills_root / skill_name / EXAMPLE_PROMPTS_DIR).is_dir()
                        self.skills_prompts_url[skill_name] = (
                            f"https://github.com/open-edge-platform/skills/tree/{ref}/.agents/skills/{skill_name}/{EXAMPLE_PROMPTS_DIR}"
                            if has_prompts else ""
                        )
            
            print(f"✅ Loaded skills config: {len(self.skills_config)} skills mapped")
        except Exception as e:
            print(f"⚠️ Error loading skills config: {e}")

    def extract_component_name(self, skill_name: str) -> str:
        """Extract component name from skills-config.json or fallback to deriving from skill name"""
        # First try to get component from skills-config
        if skill_name in self.skills_config:
            return self.skills_config[skill_name]
        
        # Fallback: extract from skill name (e.g., 'chatqna' from 'chatqna-docker-deploy')
        parts = skill_name.split('-')
        if len(parts) >= 2:
            return parts[0]
        return skill_name

    def load_validator_data(self, validator_json: str) -> None:
        """Load validator results from JSON file"""
        try:
            with open(validator_json, 'r') as f:
                data = json.load(f)
                self.validator_data = data.get('skills', {})
                print(f"✅ Loaded validator data: {len(self.validator_data)} skills")
        except Exception as e:
            print(f"⚠️ Error loading validator data: {e}")

    def load_spector_data(self, spector_json: str) -> None:
        """Load spector results from JSON file"""
        try:
            with open(spector_json, 'r') as f:
                data = json.load(f)
                self.spector_data = data.get('skills', {})
                print(f"✅ Loaded spector data: {len(self.spector_data)} skills")
        except Exception as e:
            print(f"⚠️ Error loading spector data: {e}")

    def load_bandit_data(self, bandit_json: str) -> None:
        """Load Bandit security scan results (repo-wide + per-skill) from JSON file"""
        try:
            with open(bandit_json, 'r') as f:
                data = json.load(f)
            if not data.get('available', False):
                print("⚠️ Bandit data not available")
                return
            self.bandit_data = data.get('skills', {})
            self.bandit_repo_totals = {
                'high': data.get('total_high', 0),
                'medium': data.get('total_medium', 0),
                'low': data.get('total_low', 0),
                'issues': data.get('total_issues', 0),
            }
            print(f"✅ Loaded Bandit data: {len(self.bandit_data)} skills with findings, "
                  f"{self.bandit_repo_totals['issues']} total issues repo-wide")
        except Exception as e:
            print(f"⚠️ Error loading Bandit data: {e}")

    def load_zizmor_data(self, zizmor_json: str) -> None:
        """Load Zizmor GitHub Actions workflow scan results from JSON file"""
        try:
            with open(zizmor_json, 'r') as f:
                data = json.load(f)
            if not data.get('available', False):
                print("⚠️ Zizmor data not available")
                return
            self.zizmor_data = data
            print(f"✅ Loaded Zizmor data: {data.get('total_issues', 0)} findings")
        except Exception as e:
            print(f"⚠️ Error loading Zizmor data: {e}")

    def load_scorecard_data(self, scorecard_json: str) -> None:
        """Load OpenSSF Scorecard results from JSON file"""
        try:
            with open(scorecard_json, 'r') as f:
                data = json.load(f)
            if not data.get('available', False):
                print("⚠️ Scorecard data not available")
                return
            self.scorecard_data = data
            print(f"✅ Loaded OpenSSF Scorecard data: score {data.get('score', 'N/A')}/10")
        except Exception as e:
            print(f"⚠️ Error loading Scorecard data: {e}")

    def parse_benchmark_file(self, skill_path: Path) -> Dict:
        """Parse benchmark/benchmark.md file"""
        benchmark_file = skill_path / 'benchmark' / 'benchmark.md'

        result = {
            'eval_pass_rate': 'Not Available',
            'eval_uplift': 'Not Available',
            'evals_with_skill': 'Not Available',
            'evals_total': 'Not Available',
        }

        if not benchmark_file.exists():
            return result

        try:
            content = benchmark_file.read_text()

            # Extract evals passed (w/ skill): row format | Copilot ... | 0 / 12 | 8 / 12 | **+8 ↑** |
            evals_match = re.search(
                r'### Evals passed[^\n]*\n(?:.*\n){0,5}?\|\s*Copilot[^|]*\|[^|]+\|\s*(\d+)\s*/\s*(\d+)',
                content, re.IGNORECASE
            )
            if evals_match:
                result['evals_with_skill'] = evals_match.group(1)
                result['evals_total'] = evals_match.group(2)

            # Extract pass rate % and uplift: row format | Copilot ... | 10% ±21% | 87% ±22% | **+76pp ↑** |
            pass_rate_match = re.search(
                r'### Pass rate[^\n]*\n(?:.*\n){0,5}?\|\s*Copilot[^|]*\|[^|]+\|\s*(\d+)%[^|]*\|\s*\*\*([+\-]\d+pp)',
                content, re.IGNORECASE
            )
            if pass_rate_match:
                result['eval_pass_rate'] = f"{pass_rate_match.group(1)}%"
                result['eval_uplift'] = pass_rate_match.group(2)

        except Exception as e:
            print(f"Error parsing benchmark file {benchmark_file}: {e}")

        return result

    def parse_evals_json(self, skill_path: Path) -> int:
        """Parse evals/evals.json to get number of eval tests"""
        evals_file = skill_path / 'evals' / 'evals.json'
        
        if not evals_file.exists():
            return 0
            
        try:
            with open(evals_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'evals' in data:
                    return len(data.get('evals', []))
                elif isinstance(data, list):
                    return len(data)
        except Exception as e:
            print(f"Error parsing evals.json: {e}")
            
        return 0

    def parse_skill_metadata(self, skill_path: Path) -> Dict:
        """Parse skill metadata from skill.yaml or manifest files"""
        metadata = {
            'description': '',
            'model': 'Unknown',
            'loc': 0,
            'files': []
        }
        
        # Look for skill configuration files
        config_files = list(skill_path.glob('*.yaml')) + list(skill_path.glob('*.yml'))
        
        for config_file in config_files:
            try:
                with open(config_file, 'r') as f:
                    content = f.read()
                    if 'description' in content:
                        desc_match = re.search(r'description[:\s]+"([^"]+)"', content)
                        if desc_match:
                            metadata['description'] = desc_match.group(1)
            except:
                pass
        
        # Count lines of code (Python, JS, etc.)
        code_extensions = ['.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.sh']
        for ext in code_extensions:
            for file in skill_path.glob(f'**/*{ext}'):
                try:
                    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                        metadata['loc'] += len(f.readlines())
                except:
                    pass
        
        return metadata

    def scan_skills(self):
        """Scan all skills directories"""
        for skill_dir in self.skills_root.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                continue
                
            skill_name = skill_dir.name
            component = self.extract_component_name(skill_name)
            
            # Parse benchmark data
            benchmark = self.parse_benchmark_file(skill_dir)
            
            # Parse evals count
            eval_count = self.parse_evals_json(skill_dir)
            
            # Parse metadata
            metadata = self.parse_skill_metadata(skill_dir)
            
            # Store skill data
            skill_data = {
                'name': skill_name,
                'component': component,
                'benchmark': benchmark,
                'eval_count': eval_count,
                'metadata': metadata,
                'path': str(skill_dir)
            }
            
            self.skills_data[skill_name] = skill_data
            
            # Aggregate component data
            self.components[component]['skills'].append(skill_name)
            self.components[component]['total_eval_tests'] += eval_count
            self.components[component]['total_loc'] += metadata['loc']
            
            # Store benchmark metrics
            for key, value in benchmark.items():
                if value != 'Not Available':
                    if key not in self.components[component]['eval_metrics']:
                        self.components[component]['eval_metrics'][key] = []
                    self.components[component]['eval_metrics'][key].append(value)

    def calculate_component_metrics(self):
        """Calculate aggregated metrics per component"""
        for component, data in self.components.items():
            # Calculate average pass rate
            pass_rates = data['eval_metrics'].get('eval_pass_rate', [])
            if pass_rates:
                numeric_rates = []
                for rate in pass_rates:
                    match = re.search(r'(\d+)', str(rate))
                    if match:
                        numeric_rates.append(int(match.group(1)))
                if numeric_rates:
                    data['avg_pass_rate'] = sum(numeric_rates) / len(numeric_rates)
            
            # Calculate average uplift
            uplifts = data['eval_metrics'].get('eval_uplift', [])
            if uplifts:
                numeric_uplifts = []
                for uplift in uplifts:
                    match = re.search(r'([±+\-]?\d+\.?\d*)', str(uplift))
                    if match:
                        numeric_uplifts.append(float(match.group(1)))
                if numeric_uplifts:
                    data['avg_uplift'] = sum(numeric_uplifts) / len(numeric_uplifts)

    def format_spector_vulnerabilities(self, spector_vulns: Optional[Dict], inline_styles: bool = False) -> Tuple[str, str]:
        """Format SkillSpector results for an HTML or Markdown report cell."""
        if spector_vulns is None:
            return "N/A", "metric-neutral"

        critical = spector_vulns.get('critical', 0)
        high = spector_vulns.get('high', 0)
        medium = spector_vulns.get('medium', 0)
        low = spector_vulns.get('low', 0)
        total = spector_vulns.get('issues', critical + high + medium + low)
        score = spector_vulns.get('score', 0)
        severity = spector_vulns.get('severity', '')
        recommendation = spector_vulns.get('recommendation', '')
        severity_display = severity or 'UNKNOWN'
        recommendation_icon = '✅' if recommendation == 'SAFE' else '❌'
        recommendation_display = f"{recommendation_icon} {recommendation or 'N/A'}"

        severity_colors = {
            'LOW': '#27ae60',
            'MEDIUM': '#f39c12',
            'HIGH': '#e67e22',
            'CRITICAL': '#e74c3c',
        }
        recommendation_colors = {
            'SAFE': '#27ae60',
            'CAUTION': '#f39c12',
            'DO NOT INSTALL': '#e74c3c',
        }

        if inline_styles:
            severity_text = f'<span style="color: {severity_colors.get(severity, "#7f8c8d")}; font-weight: 600;">{severity_display}</span>'
            recommendation_text = f'<span style="color: {recommendation_colors.get(recommendation, "#7f8c8d")}; font-weight: 600;">{recommendation_display}</span>'
        else:
            severity_class = f"severity-{severity.lower()}" if severity else 'metric-neutral'
            recommendation_class = (
                f"recommendation-{recommendation.lower().replace(' ', '-')}"
                if recommendation else 'metric-neutral'
            )
            severity_text = f'<span class="{severity_class}">{severity_display}</span>'
            recommendation_text = f'<span class="{recommendation_class}">{recommendation_display}</span>'

        parts = [
            f"Score: {score}/100",
            f"Severity: {severity_text}",
            f"Recommendation: {recommendation_text}",
            f"Issues: {total}",
        ]
        counts = [(critical, '🔴', 'C'), (high, '🟠', 'H'), (medium, '🟡', 'M'), (low, '🔵', 'L')]
        count_display = [f"{icon} {count}{label}" for count, icon, label in counts if count > 0]
        if count_display:
            parts.append("Counts: " + ", ".join(count_display))

        display_class = 'metric-warning' if critical > 0 or high > 0 else 'metric-good'
        return "<br>".join(parts), display_class

    def format_bandit_findings(self, bandit_findings: Optional[Dict]) -> Tuple[str, str]:
        """Format per-skill Bandit results for an HTML/Markdown report cell."""
        if self.bandit_repo_totals is None:
            return "N/A", "metric-neutral"

        if bandit_findings is None:
            return "✅ 0 issues", "metric-good"

        high = bandit_findings.get('high', 0)
        medium = bandit_findings.get('medium', 0)
        low = bandit_findings.get('low', 0)
        issues = bandit_findings.get('issues', high + medium + low)

        counts = [(high, '🟠', 'H'), (medium, '🟡', 'M'), (low, '🔵', 'L')]
        count_display = [f"{icon} {count}{label}" for count, icon, label in counts if count > 0]

        status_icon = "❌" if high > 0 or medium > 0 else ("⚠️" if issues > 0 else "✅")
        parts = [f"{status_icon} {issues} issues"]
        if count_display:
            parts.append("Counts: " + ", ".join(count_display))

        display_class = 'metric-warning' if high > 0 or medium > 0 else ('metric-neutral' if issues > 0 else 'metric-good')
        return "<br>".join(parts), display_class

    def generate_html_report(self) -> str:
        """Generate comprehensive HTML report with industry standards"""
        self.calculate_component_metrics()
        
        # Add timestamp and counts
        total_skills = len(self.skills_data)
        total_components = len(self.components)
        total_evals = sum(skill['eval_count'] for skill in self.skills_data.values())
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skill Compliance Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); color: #2c3e50; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; }}
        header h1 {{ font-size: 2.5em; margin-bottom: 10px; font-weight: 700; }}
        header p {{ font-size: 1.1em; opacity: 0.95; margin-top: 10px; }}
        .report-meta {{ background: #f8f9fa; padding: 20px 40px; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 20px; }}
        .meta-item {{ display: flex; align-items: center; gap: 10px; }}
        .meta-label {{ font-weight: 600; color: #667eea; }}
        .meta-value {{ color: #2c3e50; font-size: 0.95em; }}
        .content {{ padding: 40px; }}
        .section {{ margin-bottom: 40px; }}
        .section-title {{ font-size: 1.8em; color: #667eea; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 3px solid #667eea; }}
        .subsection-title {{ font-size: 1.3em; color: #764ba2; margin-top: 30px; margin-bottom: 15px; font-weight: 600; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05); border-radius: 6px; overflow: hidden; }}
        th {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 16px; text-align: left; font-weight: 600; font-size: 0.95em; }}
        td {{ padding: 14px 16px; border-bottom: 1px solid #e0e0e0; }}
        tr:hover {{ background: #f8f9fa; transition: background 0.2s ease; }}
        .metric-good {{ color: #27ae60; font-weight: 600; }}
        .metric-warning {{ color: #f39c12; font-weight: 600; }}
        .metric-neutral {{ color: #7f8c8d; }}
        .severity-low, .recommendation-safe {{ color: #27ae60; font-weight: 600; }}
        .severity-medium, .recommendation-caution {{ color: #f39c12; font-weight: 600; }}
        .severity-high {{ color: #e67e22; font-weight: 600; }}
        .severity-critical, .recommendation-do-not-install {{ color: #e74c3c; font-weight: 600; }}
        .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; display: inline-block; margin-right: 15px; }}
        .stat-card h3 {{ font-size: 2em; margin-bottom: 5px; }}
        .stat-card p {{ font-size: 0.9em; opacity: 0.9; }}
        .skill-card {{ background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; margin-bottom: 12px; transition: all 0.3s ease; }}
        .skill-card:hover {{ border-color: #667eea; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.1); }}
        .skill-name {{ font-weight: 700; color: #667eea; margin-bottom: 8px; }}
        .skill-details {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; font-size: 0.9em; }}
        .skill-detail-item {{ display: flex; justify-content: space-between; padding: 6px 0; }}
        .detail-label {{ color: #7f8c8d; font-weight: 500; }}
        .detail-value {{ color: #2c3e50; font-weight: 600; }}
        .summary-table {{ width: 100%; margin-bottom: 30px; }}
        .summary-table th, .summary-table td {{ text-align: center; }}
        .summary-table th:first-child, .summary-table td:first-child {{ text-align: left; }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 600; }}
        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .badge-info {{ background: #d1ecf1; color: #0c5460; }}
        .benchmark-section {{ background: #f8f9fa; border-left: 4px solid #667eea; padding: 16px; border-radius: 4px; margin-bottom: 20px; }}
        .footer {{ background: #f8f9fa; border-top: 1px solid #e0e0e0; padding: 20px 40px; text-align: center; color: #7f8c8d; font-size: 0.9em; }}
        .skill-details-table th:nth-child(1), .skill-details-table th:nth-child(2), .skill-details-table td:nth-child(1), .skill-details-table td:nth-child(2) {{ text-align: center; }}
        @media (max-width: 768px) {{ header h1 {{ font-size: 1.8em; }} .report-meta {{ flex-direction: column; align-items: flex-start; }} .skill-details {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 Skill Compliance Report</h1>
            <p>Comprehensive Quality and Performance Assessment</p>
        </header>
        
        <div class="report-meta">
            <div class="meta-item">
                <span class="meta-label">Generated:</span>
                <span class="meta-value">{timestamp}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Total Components:</span>
                <span class="meta-value">{total_components}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Total Skills:</span>
                <span class="meta-value">{total_skills}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Total Eval Tests:</span>
                <span class="meta-value">{total_evals}</span>
            </div>
        </div>
        
        <div class="content">
"""
        
        # Executive Summary Section
        html += self._generate_executive_summary()
        
        # Component Summary Table
        html += self._generate_component_summary_table()
        
        # Skills Detail Report
        html += self._generate_skills_detail()
        
        # Repository-wide security scans
        html += self._generate_security_scans_section()
        
        # Footer
        html += """
        </div>
        <div class="footer">
            <p>This report is generated automatically. For more information, visit the skills repository documentation.</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html

    def _generate_executive_summary(self) -> str:
        """Generate executive summary section"""
        html = """
            <div class="section">
                <h2 class="section-title">📊 Executive Summary</h2>
                <div style="margin-bottom: 20px;">
"""
        
        # Key statistics
        total_skills = len(self.skills_data)
        total_evals = sum(skill['eval_count'] for skill in self.skills_data.values())
        skills_with_evals = sum(1 for skill in self.skills_data.values() if skill['eval_count'] > 0)
        
        html += f"""
                    <div class="stat-card">
                        <h3>{total_skills}</h3>
                        <p>Total Skills</p>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                        <h3>{total_evals}</h3>
                        <p>Evaluation Tests</p>
                    </div>
                    <div class="stat-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                        <h3>{skills_with_evals}</h3>
                        <p>Skills with Benchmarks</p>
                    </div>
                </div>
            </div>
"""
        return html

    def _generate_component_summary_table(self) -> str:
        """Generate component summary table with skill count"""
        html = """
            <div class="section">
                <h2 class="section-title">📈 Component Summary</h2>
                <table class="summary-table">
                    <thead>
                        <tr>
                            <th>Component</th>
                            <th>Number of Skills</th>
                            <th>Skills</th>
                        </tr>
                    </thead>
                    <tbody>
"""
        
        for component in sorted(self.components.keys()):
            data = self.components[component]
            skills_list = ', '.join(sorted(data['skills']))
            num_skills = len(data['skills'])
            
            html += f"""
                        <tr>
                            <td><strong>{component}</strong></td>
                            <td style="text-align: center;"><strong>{num_skills}</strong></td>
                            <td>{skills_list}</td>
                        </tr>
"""
        
        html += """
                    </tbody>
                </table>
            </div>
"""
        return html

    def _generate_component_details(self) -> str:
        """Generate detailed component reports"""
        html = """
            <div class="section">
                <h2 class="section-title">🔍 Component Analysis</h2>
"""
        
        for component in sorted(self.components.keys()):
            data = self.components[component]
            
            html += f"""
                <div class="subsection-title">{component.upper()} Component</div>
                <div class="benchmark-section">
                    <p><strong>Skills:</strong> {', '.join(sorted(data['skills']))}</p>
                    <p><strong>Evaluation Tests:</strong> {data['total_eval_tests']}</p>
                    <p><strong>Total Lines of Code:</strong> {data['total_loc']:,}</p>
"""
            
            if data.get('avg_pass_rate'):
                html += f"                    <p><strong>Average Pass Rate:</strong> <span class='metric-good'>{data['avg_pass_rate']:.1f}%</span></p>"
            
            if data.get('avg_uplift'):
                html += f"                    <p><strong>Average Uplift:</strong> <span class='metric-good'>{data['avg_uplift']:+.1f}pp</span></p>"
            
            html += """
                </div>
"""
        
        html += """
            </div>
"""
        return html

    def _generate_skills_detail(self) -> str:
        """Generate detailed skills report as a comprehensive table"""
        html = """
            <div class="section">
                <h2 class="section-title">📋 Skill Details</h2>
                <table class="skill-details-table">
                    <thead>
                        <tr>
                            <th>Skill Name</th>
                            <th>Component</th>
                            <th>Evals Passed</th>
                            <th>Skill Uplift</th>
                            <th>skill-validator metrics</th>
                            <th>skillspector vulnerabilities</th>
                            <th>Bandit scan</th>
                            <th>Example Prompts</th>
                        </tr>
                    </thead>
                    <tbody>
"""
        
        for skill_name in sorted(self.skills_data.keys()):
            skill = self.skills_data[skill_name]
            benchmark = skill['benchmark']
            
            pass_rate = benchmark['eval_pass_rate']
            
            # Use directly parsed evals_with_skill / evals_total from benchmark
            evals_with = benchmark.get('evals_with_skill', 'Not Available')
            evals_total_bm = benchmark.get('evals_total', 'Not Available')
            if evals_with != 'Not Available' and evals_total_bm != 'Not Available':
                pass_rate_display = f"{evals_with}/{evals_total_bm}"
            else:
                pass_rate_display = "N/A"

            # Apply color coding for pass rate
            pass_rate_class = 'metric-good' if pass_rate != 'Not Available' and pass_rate.rstrip('%').isdigit() and int(pass_rate.rstrip('%')) > 80 else 'metric-neutral' if pass_rate == 'Not Available' else 'metric-warning'
            
            # Format uplift
            uplift_raw = benchmark['eval_uplift']
            uplift_class = 'metric-good' if uplift_raw != 'Not Available' else 'metric-neutral'
            uplift_display = uplift_raw if uplift_raw != 'Not Available' else 'N/A'
            
            # Get validator metrics — distinguish no-data (None) from a passing run ({})
            validator_metrics = self.validator_data.get(skill_name)
            if validator_metrics is None:
                validator_display = "N/A"
                validator_class = 'metric-neutral'
            else:
                validator_errors = validator_metrics.get('errors', 0)
                validator_warnings = validator_metrics.get('warnings', 0)
                validator_tokens = validator_metrics.get('tokens_used', 0)
                validator_status = "Fail" if validator_errors > 0 else "Pass"
                status_color = '#27ae60' if validator_status == "Pass" else '#e74c3c'
                status_span = f'<span style="color: {status_color}; font-weight: 600;">{validator_status}</span>'
                validator_parts = [status_span]
                if validator_errors > 0:
                    validator_parts.append(f"Errors: {validator_errors}")
                if validator_warnings > 0:
                    validator_parts.append(f"Warnings: {validator_warnings}")
                if validator_tokens > 0:
                    validator_parts.append(f"Total Tokens: {validator_tokens}")
                validator_display = "<br>".join(validator_parts)
                validator_class = 'metric-good' if validator_status == "Pass" else 'metric-warning'
            
            # Get spector vulnerabilities — distinguish no-data (None) from a clean scan
            spector_display, spector_class = self.format_spector_vulnerabilities(
                self.spector_data.get(skill_name)
            )

            # Get Bandit findings for this skill — distinguish no-data (None) from a clean scan
            bandit_display, bandit_class = self.format_bandit_findings(
                self.bandit_data.get(skill_name)
            )
            
            prompts_url = self.skills_prompts_url.get(skill_name, "")
            prompts_cell = f'<a href="{prompts_url}">View</a>' if prompts_url else "N/A"

            html += f"""
                        <tr>
                            <td><strong>{skill_name}</strong></td>
                            <td>{skill['component']}</td>
                            <td class="{pass_rate_class}">{pass_rate_display}</td>
                            <td class="{uplift_class}">{uplift_display}</td>
                            <td class="{validator_class}">{validator_display}</td>
                            <td class="{spector_class}">{spector_display}</td>
                            <td class="{bandit_class}">{bandit_display}</td>
                            <td>{prompts_cell}</td>
                        </tr>
"""
        
        html += """
                    </tbody>
                </table>
            </div>
"""
        return html

    def _generate_security_scans_section(self) -> str:
        """Generate the repository-wide security scans section (Bandit, Zizmor, OpenSSF Scorecard, CodeQL, Secret Scanning)"""
        repo = self.github_repo or "open-edge-platform/skills"
        actions_url = f"https://github.com/{repo}/actions/workflows"
        security_tab_url = f"https://github.com/{repo}/security"

        html = """
            <div class="section">
                <h2 class="section-title">🔐 Repository Security Scans</h2>
                <p style="margin-bottom: 16px; color: #7f8c8d;">
                    These scans cover the entire repository (not just individual skills) and reflect the latest
                    results at the time this report was generated.
                </p>
                <table>
                    <thead>
                        <tr>
                            <th>Scan</th>
                            <th>Status</th>
                            <th>Findings</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
"""

        # Bandit (repo-wide)
        if self.bandit_repo_totals is not None:
            t = self.bandit_repo_totals
            if t['issues'] == 0:
                bandit_status, bandit_class = "✅ Clean", "metric-good"
            elif t['high'] or t['medium']:
                bandit_status, bandit_class = "❌ Findings", "metric-warning"
            else:
                bandit_status, bandit_class = "⚠️ Low severity only", "metric-neutral"
            bandit_findings = f"🟠 {t['high']}H, 🟡 {t['medium']}M, 🔵 {t['low']}L ({t['issues']} total)"
        else:
            bandit_status, bandit_class = "N/A", "metric-neutral"
            bandit_findings = "N/A"

        html += f"""
                        <tr>
                            <td><strong>Bandit</strong> (Python SAST)</td>
                            <td class="{bandit_class}">{bandit_status}</td>
                            <td>{bandit_findings}</td>
                            <td><a href="{actions_url}/security-scan.yml">Workflow</a> &middot; <a href="{security_tab_url}/code-scanning?query=tool%3ABandit">Security tab</a></td>
                        </tr>
"""

        # Zizmor (repo-wide)
        if self.zizmor_data is not None:
            z = self.zizmor_data
            z_total = z.get('total_issues', 0)
            if z_total == 0:
                zizmor_status, zizmor_class = "✅ Clean", "metric-good"
            elif z.get('total_high') or z.get('total_medium'):
                zizmor_status, zizmor_class = "❌ Findings", "metric-warning"
            else:
                zizmor_status, zizmor_class = "⚠️ Low severity only", "metric-neutral"
            zizmor_findings = f"🟠 {z.get('total_high', 0)}H, 🟡 {z.get('total_medium', 0)}M, 🔵 {z.get('total_low', 0)}L ({z_total} total)"
        else:
            zizmor_status, zizmor_class = "N/A", "metric-neutral"
            zizmor_findings = "N/A"

        html += f"""
                        <tr>
                            <td><strong>Zizmor</strong> (GitHub Actions SAST)</td>
                            <td class="{zizmor_class}">{zizmor_status}</td>
                            <td>{zizmor_findings}</td>
                            <td><a href="{actions_url}/security-scan.yml">Workflow</a> &middot; <a href="{security_tab_url}/code-scanning?query=tool%3Azizmor">Security tab</a></td>
                        </tr>
"""

        # OpenSSF Scorecard
        if self.scorecard_data is not None:
            score = self.scorecard_data.get('score', -1)
            if isinstance(score, (int, float)) and score >= 0:
                score_display = f"{score:.1f}/10"
                if score >= 7:
                    scorecard_status, scorecard_class = "✅ Good", "metric-good"
                else:
                    scorecard_status, scorecard_class = "⚠️ Needs attention", "metric-warning"
            else:
                score_display = "N/A"
                scorecard_status, scorecard_class = "N/A", "metric-neutral"
            low_checks = [
                c['name'] for c in self.scorecard_data.get('checks', [])
                if isinstance(c.get('score'), (int, float)) and 0 <= c['score'] < 5
            ]
            scorecard_findings = f"Lowest checks: {', '.join(low_checks[:5])}" if low_checks else "No low-scoring checks"
        else:
            score_display = "N/A"
            scorecard_status, scorecard_class = "N/A", "metric-neutral"
            scorecard_findings = "N/A"

        html += f"""
                        <tr>
                            <td><strong>OpenSSF Scorecard</strong></td>
                            <td class="{scorecard_class}">{scorecard_status}</td>
                            <td>{score_display}<br>{scorecard_findings}</td>
                            <td><a href="{actions_url}/scorecards.yml">Workflow</a> &middot; <a href="https://scorecard.dev/viewer/?uri=github.com/{repo}">scorecard.dev</a></td>
                        </tr>
"""

        # CodeQL and Secret Scanning: badge-based status, per-alert counts live in the Security tab
        html += f"""
                        <tr>
                            <td><strong>CodeQL</strong></td>
                            <td><img src="{actions_url}/codeql.yml/badge.svg" alt="CodeQL status"></td>
                            <td>See Security tab</td>
                            <td><a href="{actions_url}/codeql.yml">Workflow</a> &middot; <a href="{security_tab_url}/code-scanning?query=tool%3ACodeQL">Security tab</a></td>
                        </tr>
                        <tr>
                            <td><strong>Secret Scanning</strong></td>
                            <td><img src="{actions_url}/secret-scan.yml/badge.svg" alt="Secret scan status"></td>
                            <td>See Security tab</td>
                            <td><a href="{actions_url}/secret-scan.yml">Workflow</a> &middot; <a href="{security_tab_url}/secret-scanning">Secret scanning alerts</a></td>
                        </tr>
                        <tr>
                            <td><strong>SkillSpector / skill-validator</strong></td>
                            <td><img src="{actions_url}/skill-scan.yml/badge.svg" alt="Skill scanner status"></td>
                            <td>See Skill Details table above</td>
                            <td><a href="{actions_url}/skill-scan.yml">Workflow</a></td>
                        </tr>
"""

        html += """
                    </tbody>
                </table>
            </div>
"""
        return html

    def _generate_compliance_standards(self) -> str:
        """Generate compliance standards section"""
        html = """
            <div class="section">
                <h2 class="section-title">✅ Quality Standards & Compliance</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Standard</th>
                            <th>Criterion</th>
                            <th>Status</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>Testing Coverage</strong></td>
                            <td>Evaluation tests defined</td>
                            <td><span class="badge badge-success">✓ PASS</span></td>
                            <td>Multiple skills have evaluation tests defined</td>
                        </tr>
                        <tr>
                            <td><strong>Code Quality</strong></td>
                            <td>LOC consistency</td>
                            <td><span class="badge badge-info">ℹ INFO</span></td>
                            <td>All skills have code implementations with measurable LOC</td>
                        </tr>
                        <tr>
                            <td><strong>Benchmarking</strong></td>
                            <td>Performance metrics available</td>
                            <td><span class="badge badge-info">ℹ INFO</span></td>
                            <td>Benchmark data available for performance evaluation</td>
                        </tr>
                        <tr>
                            <td><strong>Documentation</strong></td>
                            <td>Skill metadata</td>
                            <td><span class="badge badge-success">✓ PASS</span></td>
                            <td>All skills have configuration and metadata files</td>
                        </tr>
                        <tr>
                            <td><strong>Validation</strong></td>
                            <td>Structure compliance</td>
                            <td><span class="badge badge-success">✓ PASS</span></td>
                            <td>All skills follow the standard skill directory structure</td>
                        </tr>
                    </tbody>
                </table>
            </div>
"""
        return html

    def generate_markdown_summary(self) -> str:
        """Generate Markdown summary for GitHub Actions job summary ($GITHUB_STEP_SUMMARY)"""
        self.calculate_component_metrics()

        total_skills = len(self.skills_data)
        total_evals = sum(s['eval_count'] for s in self.skills_data.values())
        skills_with_evals = sum(1 for s in self.skills_data.values() if s['eval_count'] > 0)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = ["# Skill Compliance Report", ""]

        if self.github_run_id and self.github_repo:
            run_url = f"https://github.com/{self.github_repo}/actions/runs/{self.github_run_id}"
            lines.append(f"**Generated:** {timestamp} &nbsp;|&nbsp; **Run:** [{self.github_run_id}]({run_url})")
        else:
            lines.append(f"**Generated:** {timestamp}")
        lines.append("")

        # Match HTML Executive Summary stat cards
        lines += [
            "## Executive Summary",
            "",
            "| Total Skills | Evaluation Tests | Skills with Benchmarks |",
            "|:---:|:---:|:---:|",
            f"| {total_skills} | {total_evals} | {skills_with_evals} |",
            "",
        ]

        # Match HTML Component Summary: Component | Number of Skills | Skills (list)
        lines += [
            "## Component Summary",
            "",
            "| Component | Number of Skills | Skills |",
            "|---|:---:|---|",
        ]
        for component in sorted(self.components.keys()):
            data = self.components[component]
            skills_list = ", ".join(sorted(data['skills']))
            lines.append(f"| **{component}** | {len(data['skills'])} | {skills_list} |")

        # Match HTML Skill Details columns and formatting exactly
        lines += [
            "",
            "## Skill Details",
            "",
            "| Skill Name | Component | Evals Passed | Skill Uplift | skill-validator metrics | skillspector vulnerabilities | Bandit scan | Example Prompts |",
            "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
        ]
        for skill_name in sorted(self.skills_data.keys()):
            skill = self.skills_data[skill_name]
            benchmark = skill['benchmark']
            pass_rate = benchmark['eval_pass_rate']

            # Use directly parsed evals_with_skill / evals_total from benchmark
            evals_with = benchmark.get('evals_with_skill', 'Not Available')
            evals_total_bm = benchmark.get('evals_total', 'Not Available')
            if evals_with != 'Not Available' and evals_total_bm != 'Not Available':
                pass_rate_display = f"{evals_with}/{evals_total_bm}"
            else:
                pass_rate_display = "N/A"

            uplift_display = benchmark['eval_uplift'] if benchmark['eval_uplift'] != 'Not Available' else 'N/A'

            # Match HTML validator display: Status / Tokens / Errors+Warnings
            validator_metrics = self.validator_data.get(skill_name)
            if validator_metrics is not None:
                v_errors = validator_metrics.get('errors', 0)
                v_warnings = validator_metrics.get('warnings', 0)
                v_tokens = validator_metrics.get('tokens_used', 0)
                v_status = "Fail" if v_errors > 0 else "Pass"
                status_icon = "✅" if v_status == "Pass" else "❌"
                v_parts = [f"{status_icon} {v_status}"]
                if v_errors > 0:
                    v_parts.append(f"Errors: {v_errors}")
                if v_warnings > 0:
                    v_parts.append(f"Warnings: {v_warnings}")
                if v_tokens > 0:
                    v_parts.append(f"Total Tokens: {v_tokens}")
                validator_cell = "<br>".join(v_parts)
            else:
                validator_cell = "N/A"

            # Match HTML spector display — distinguish no-data (None) from a clean scan
            spector_cell, _ = self.format_spector_vulnerabilities(
                self.spector_data.get(skill_name), inline_styles=True
            )

            # Match HTML Bandit display — distinguish no-data (None) from a clean scan
            bandit_cell, _ = self.format_bandit_findings(self.bandit_data.get(skill_name))

            prompts_url = self.skills_prompts_url.get(skill_name, "")
            prompts_cell = f"[View]({prompts_url})" if prompts_url else "N/A"

            lines.append(
                f"| **{skill_name}** | {skill['component']} "
                f"| {pass_rate_display} | {uplift_display} "
                f"| {validator_cell} | {spector_cell} | {bandit_cell} | {prompts_cell} |"
            )

        # Repository-wide security scans (Bandit, Zizmor, OpenSSF Scorecard)
        lines += self._generate_security_scans_markdown()

        return "\n".join(lines) + "\n"

    def _generate_security_scans_markdown(self) -> List[str]:
        """Generate the repository-wide security scans section for the Markdown summary"""
        repo = self.github_repo or "open-edge-platform/skills"
        actions_url = f"https://github.com/{repo}/actions/workflows"
        security_tab_url = f"https://github.com/{repo}/security"

        lines = [
            "",
            "## Repository Security Scans",
            "",
            "These scans cover the entire repository (not just individual skills) and reflect the latest results "
            "at the time this report was generated.",
            "",
            "| Scan | Status | Findings | Details |",
            "|---|:---:|:---:|---|",
        ]

        # Bandit (repo-wide)
        if self.bandit_repo_totals is not None:
            t = self.bandit_repo_totals
            bandit_status = "✅ Clean" if t['issues'] == 0 else ("❌ Findings" if (t['high'] or t['medium']) else "⚠️ Low severity only")
            bandit_findings = f"🟠 {t['high']}H, 🟡 {t['medium']}M, 🔵 {t['low']}L ({t['issues']} total)"
        else:
            bandit_status = "N/A"
            bandit_findings = "N/A"
        lines.append(
            f"| **Bandit** (Python SAST) | {bandit_status} | {bandit_findings} | "
            f"[Workflow]({actions_url}/security-scan.yml) · [Security tab]({security_tab_url}/code-scanning?query=tool%3ABandit) |"
        )

        # Zizmor (repo-wide)
        if self.zizmor_data is not None:
            z = self.zizmor_data
            z_total = z.get('total_issues', 0)
            zizmor_status = "✅ Clean" if z_total == 0 else ("❌ Findings" if (z.get('total_high') or z.get('total_medium')) else "⚠️ Low severity only")
            zizmor_findings = f"🟠 {z.get('total_high', 0)}H, 🟡 {z.get('total_medium', 0)}M, 🔵 {z.get('total_low', 0)}L ({z_total} total)"
        else:
            zizmor_status = "N/A"
            zizmor_findings = "N/A"
        lines.append(
            f"| **Zizmor** (GitHub Actions SAST) | {zizmor_status} | {zizmor_findings} | "
            f"[Workflow]({actions_url}/security-scan.yml) · [Security tab]({security_tab_url}/code-scanning?query=tool%3Azizmor) |"
        )

        # OpenSSF Scorecard
        if self.scorecard_data is not None:
            score = self.scorecard_data.get('score', -1)
            score_display = f"{score:.1f}/10" if isinstance(score, (int, float)) and score >= 0 else "N/A"
            low_checks = [c['name'] for c in self.scorecard_data.get('checks', []) if isinstance(c.get('score'), (int, float)) and 0 <= c['score'] < 5]
            scorecard_status = "✅ Good" if isinstance(score, (int, float)) and score >= 7 else ("⚠️ Needs attention" if isinstance(score, (int, float)) and score >= 0 else "N/A")
            scorecard_findings = f"Lowest checks: {', '.join(low_checks[:5])}" if low_checks else "No low-scoring checks"
        else:
            score_display = "N/A"
            scorecard_status = "N/A"
            scorecard_findings = "N/A"
        lines.append(
            f"| **OpenSSF Scorecard** | {scorecard_status} | {score_display} | "
            f"[Workflow]({actions_url}/scorecards.yml) · [scorecard.dev](https://scorecard.dev/viewer/?uri=github.com/{repo}) |"
        )

        # CodeQL (badge-based status; per-alert counts are in the Security tab)
        lines.append(
            f"| **CodeQL** | ![CodeQL]({actions_url}/codeql.yml/badge.svg) | See Security tab | "
            f"[Workflow]({actions_url}/codeql.yml) · [Security tab]({security_tab_url}/code-scanning?query=tool%3ACodeQL) |"
        )

        # Secret scanning (badge-based status)
        lines.append(
            f"| **Secret Scanning** | ![Secret scan]({actions_url}/secret-scan.yml/badge.svg) | See Security tab | "
            f"[Workflow]({actions_url}/secret-scan.yml) · [Secret scanning alerts]({security_tab_url}/secret-scanning) |"
        )

        # Skill scanners (per-skill results are already in the Skill Details table above)
        lines.append(
            f"| **SkillSpector / skill-validator** | ![Skill Scanner]({actions_url}/skill-scan.yml/badge.svg) | "
            f"See Skill Details table above | [Workflow]({actions_url}/skill-scan.yml) |"
        )

        lines.append("")
        return lines


def main():
    """Main entry point"""
    repo_root = Path(__file__).resolve().parent.parent
    skills_root = repo_root / ".agents/skills"
    output_file = repo_root / "skill_summary_output.html"
    skills_config_path = repo_root / "skills-config.json"

    # Check for validator and spector JSON files
    validator_json = Path("validator_results.json") if Path("validator_results.json").exists() else None
    spector_json = Path("spector_results.json") if Path("spector_results.json").exists() else None
    bandit_json = Path("bandit_results.json") if Path("bandit_results.json").exists() else None
    zizmor_json = Path("zizmor_results.json") if Path("zizmor_results.json").exists() else None
    scorecard_json = Path("scorecard_results.json") if Path("scorecard_results.json").exists() else None

    print(f"🔍 Scanning skills from: {skills_root}")
    print(f"📝 Report will be written to: {output_file}")

    if skills_config_path.exists():
        print(f"📋 Using skills config from: {skills_config_path}")
    else:
        print(f"⚠️ Skills config not found, will fallback to name-based component extraction")

    if validator_json:
        print(f"📋 Using validator data from: {validator_json}")
    else:
        print(f"⚠️ No validator JSON data found")

    if spector_json:
        print(f"🔒 Using spector data from: {spector_json}")
    else:
        print(f"⚠️ No spector JSON data found")

    if bandit_json:
        print(f"🐍 Using Bandit data from: {bandit_json}")
    else:
        print(f"⚠️ No Bandit JSON data found")

    if zizmor_json:
        print(f"⚙️ Using Zizmor data from: {zizmor_json}")
    else:
        print(f"⚠️ No Zizmor JSON data found")

    if scorecard_json:
        print(f"📊 Using Scorecard data from: {scorecard_json}")
    else:
        print(f"⚠️ No Scorecard JSON data found")

    generator = SkillComplianceReportGenerator(
        skills_root,
        str(validator_json) if validator_json else None,
        str(spector_json) if spector_json else None,
        str(skills_config_path),
        str(bandit_json) if bandit_json else None,
        str(zizmor_json) if zizmor_json else None,
        str(scorecard_json) if scorecard_json else None,
    )
    generator.scan_skills()
    
    print(f"✅ Scanned {len(generator.skills_data)} skills")
    print(f"✅ Found {len(generator.components)} components")
    
    html_content = generator.generate_html_report()

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ Report generated successfully: {output_file}")

    md_file = repo_root / "skill-compliance-report.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(generator.generate_markdown_summary())

    print(f"✅ Markdown summary written to: {md_file}")


if __name__ == '__main__':
    main()
