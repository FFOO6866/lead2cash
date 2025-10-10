#!/usr/bin/env python3
"""
Kailash Project Template Generator
Creates a new GitHub project with sprint design based on Impact-Verse template
"""

import os
import sys
import json
import yaml
import argparse
from typing import Dict, List, Optional
from pathlib import Path
import subprocess
import re

class KailashProjectGenerator:
    """Generate GitHub projects using Kailash sprint design template"""

    def __init__(self, config_path: str):
        """Initialize with configuration file"""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.gh_token = os.getenv('GH_TOKEN')

        if not self.gh_token:
            raise ValueError("GH_TOKEN environment variable not set")

    def _load_config(self) -> Dict:
        """Load YAML configuration"""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _replace_placeholders(self, template: str, values: Dict) -> str:
        """Replace {{PLACEHOLDER}} with actual values"""
        result = template
        for key, value in values.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))
        return result

    def create_github_project(self, org: str, project_name: str, description: str) -> str:
        """Create a new GitHub Project (v2)"""
        print(f"Creating GitHub Project: {project_name}")

        # GraphQL mutation to create project
        query = """
        mutation($ownerId: ID!, $title: String!, $description: String!) {
          createProjectV2(input: {ownerId: $ownerId, title: $title}) {
            projectV2 {
              id
              number
              url
            }
          }
        }
        """

        # Get organization ID
        org_query = """
        query($login: String!) {
          organization(login: $login) {
            id
          }
        }
        """

        # Execute GraphQL query to get org ID
        org_result = self._execute_graphql(org_query, {"login": org})
        org_id = org_result['data']['organization']['id']

        # Create project
        variables = {
            "ownerId": org_id,
            "title": project_name,
            "description": description
        }

        result = self._execute_graphql(query, variables)
        project_data = result['data']['createProjectV2']['projectV2']

        print(f"✓ Project created: {project_data['url']}")
        return project_data['id'], project_data['number']

    def _execute_graphql(self, query: str, variables: Dict) -> Dict:
        """Execute GitHub GraphQL API call"""
        import requests

        headers = {
            "Authorization": f"Bearer {self.gh_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "query": query,
            "variables": variables
        }

        response = requests.post(
            "https://api.github.com/graphql",
            headers=headers,
            json=payload
        )

        response.raise_for_status()
        return response.json()

    def create_project_fields(self, project_id: str):
        """Create custom fields for the project"""
        print("Creating project fields...")

        for field_config in self.config['github_automation']['project_fields']:
            field_name = field_config['name']
            field_type = field_config['type']

            print(f"  - Creating field: {field_name} ({field_type})")

            if field_type == 'single_select':
                self._create_single_select_field(project_id, field_name, field_config['options'])
            elif field_type == 'number':
                self._create_number_field(project_id, field_name)
            elif field_type == 'iteration':
                self._create_iteration_field(project_id, field_name)

    def _create_single_select_field(self, project_id: str, name: str, options: List[str]):
        """Create a single select field"""
        query = """
        mutation($projectId: ID!, $name: String!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
          createProjectV2Field(input: {
            projectId: $projectId
            dataType: SINGLE_SELECT
            name: $name
            singleSelectOptions: $options
          }) {
            projectV2Field {
              id
            }
          }
        }
        """

        option_inputs = [{"name": opt, "color": "GRAY"} for opt in options]
        variables = {
            "projectId": project_id,
            "name": name,
            "options": option_inputs
        }

        self._execute_graphql(query, variables)

    def _create_number_field(self, project_id: str, name: str):
        """Create a number field"""
        query = """
        mutation($projectId: ID!, $name: String!) {
          createProjectV2Field(input: {
            projectId: $projectId
            dataType: NUMBER
            name: $name
          }) {
            projectV2Field {
              id
            }
          }
        }
        """

        variables = {
            "projectId": project_id,
            "name": name
        }

        self._execute_graphql(query, variables)

    def _create_iteration_field(self, project_id: str, name: str):
        """Create an iteration field (Sprint)"""
        query = """
        mutation($projectId: ID!, $name: String!) {
          createProjectV2Field(input: {
            projectId: $projectId
            dataType: ITERATION
            name: $name
          }) {
            projectV2Field {
              id
            }
          }
        }
        """

        variables = {
            "projectId": project_id,
            "name": name
        }

        self._execute_graphql(query, variables)

    def create_story_0_issue(self, org: str, repo: str, project_id: str) -> str:
        """Create Story 0 infrastructure issue"""
        print("Creating Story 0 (Infrastructure) issue...")

        # Load Story 0 template
        template_path = Path(__file__).parent.parent / '.github' / 'ISSUE_TEMPLATE' / 'story-0-infrastructure.md'
        with open(template_path, 'r') as f:
            template = f.read()

        # Prepare replacement values
        values = {
            'PROJECT_NAME': self.config['project']['name'],
            'INFRASTRUCTURE_STORY_POINTS': self.config['story_0']['story_points'],
            'INFRASTRUCTURE_EFFORT_WEEKS': self.config['story_0']['effort']['weeks'],
            'INFRASTRUCTURE_EFFORT_HOURS': self.config['story_0']['effort']['hours'],
            'FRONTEND_FRAMEWORK': self.config['technology']['frontend']['framework'],
            'SETUP_SPRINT_DAYS': self.config['story_0']['setup_sprint_days'],
            'CORE_MODEL_NAME': self.config['story_0']['core_model_name'],
            'MOBILE_BREAKPOINT': self.config['technology']['frontend']['responsive_breakpoints']['mobile'],
            'TABLET_BREAKPOINT': self.config['technology']['frontend']['responsive_breakpoints']['tablet'],
            'DESKTOP_BREAKPOINT': self.config['technology']['frontend']['responsive_breakpoints']['desktop'],
            'DESIGN_SYSTEM_PATH': self.config['story_0']['design_system_path'],
            'TEST_DATA_SIZE': self.config['story_0']['test_data_size'],
            'PERF_TEST_SIZE': self.config['story_0']['perf_test_size'],
            'QUERY_PERF_MS': self.config['story_0']['performance_benchmarks']['query_ms'],
            'FILTER_PERF_MS': self.config['story_0']['performance_benchmarks']['filter_ms'],
            'SDK_INSTALL_HOURS': self.config['story_0']['time_estimates']['sdk_install'],
            'DATAFLOW_VALIDATION_HOURS': self.config['story_0']['time_estimates']['dataflow_validation'],
            'NEXUS_TEST_HOURS': self.config['story_0']['time_estimates']['nexus_test'],
            'DESIGN_SYSTEM_HOURS': self.config['story_0']['time_estimates']['design_system'],
            'API_TOOLING_HOURS': self.config['story_0']['time_estimates']['api_tooling'],
            'ENV_VALIDATION_HOURS': self.config['story_0']['time_estimates']['env_validation'],
            'KAILASH_DOCS_URL': self.config['technology']['documentation']['kailash_docs_url'],
            'DATAFLOW_DOCS_URL': self.config['technology']['documentation']['dataflow_docs_url'],
            'NEXUS_DOCS_URL': self.config['technology']['documentation']['nexus_docs_url'],
            'ARCHITECTURE_DOC_URL': self.config['technology']['documentation'].get('architecture_doc_url', 'TBD'),
        }

        # Remove frontmatter from template
        template_body = re.sub(r'^---\n.*?\n---\n', '', template, flags=re.DOTALL)

        # Replace placeholders
        issue_body = self._replace_placeholders(template_body, values)

        # Create issue via GitHub API
        import requests

        headers = {
            "Authorization": f"Bearer {self.gh_token}",
            "Accept": "application/vnd.github+json"
        }

        data = {
            "title": f"Story 0: Project Setup & Foundations (Infrastructure)",
            "body": issue_body,
            "labels": ["infrastructure", "story-0", "critical", "kailash-sdk"]
        }

        response = requests.post(
            f"https://api.github.com/repos/{org}/{repo}/issues",
            headers=headers,
            json=data
        )

        response.raise_for_status()
        issue_data = response.json()

        print(f"✓ Story 0 issue created: {issue_data['html_url']}")
        return issue_data['node_id'], issue_data['number']

    def add_issue_to_project(self, project_id: str, issue_node_id: str):
        """Add an issue to the project"""
        query = """
        mutation($projectId: ID!, $contentId: ID!) {
          addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
            item {
              id
            }
          }
        }
        """

        variables = {
            "projectId": project_id,
            "contentId": issue_node_id
        }

        self._execute_graphql(query, variables)
        print("✓ Issue added to project")

    def generate_project(self, org: str, repo: str, project_name: str, description: str):
        """Main method to generate complete project"""
        print("=" * 60)
        print("Kailash Project Template Generator")
        print("=" * 60)

        # Step 1: Create GitHub Project
        project_id, project_number = self.create_github_project(org, project_name, description)

        # Step 2: Create custom fields
        self.create_project_fields(project_id)

        # Step 3: Create Story 0 issue
        issue_node_id, issue_number = self.create_story_0_issue(org, repo, project_id)

        # Step 4: Add Story 0 to project
        self.add_issue_to_project(project_id, issue_node_id)

        print("\n" + "=" * 60)
        print("✓ Project setup complete!")
        print("=" * 60)
        print(f"Project URL: https://github.com/orgs/{org}/projects/{project_number}")
        print(f"Story 0 Issue: https://github.com/{org}/{repo}/issues/{issue_number}")
        print("\nNext steps:")
        print("1. Review and customize Story 0 issue")
        print("2. Create feature stories using the feature-story.md template")
        print("3. Begin Story 0 validation sprint")
        print("=" * 60)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Generate GitHub project using Kailash sprint design template'
    )

    parser.add_argument(
        '--config',
        default='.github/project-template-config.yaml',
        help='Path to configuration file'
    )

    parser.add_argument(
        '--org',
        required=True,
        help='GitHub organization name'
    )

    parser.add_argument(
        '--repo',
        required=True,
        help='GitHub repository name'
    )

    parser.add_argument(
        '--name',
        required=True,
        help='Project name'
    )

    parser.add_argument(
        '--description',
        default='',
        help='Project description'
    )

    args = parser.parse_args()

    # Check for GH_TOKEN
    if not os.getenv('GH_TOKEN'):
        print("Error: GH_TOKEN environment variable not set", file=sys.stderr)
        print("Please set your GitHub Personal Access Token:", file=sys.stderr)
        print("  export GH_TOKEN=your_token_here", file=sys.stderr)
        sys.exit(1)

    try:
        generator = KailashProjectGenerator(args.config)
        generator.generate_project(args.org, args.repo, args.name, args.description)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
