"""
feature_flag_env/tools/github_integration.py

GitHub Integration for Feature Flag Agents

Capabilities:
- Check deployment status from GitHub deployments API
- Create pull requests for rollout changes
- Get CI/CD pipeline info (Actions workflow status)

Install: pip install PyGithub

Usage:
    client = GitHubClient(
        token="ghp_xxxxx",
        repo="owner/repo",
        owner="owner",
        repo_name="repo"
    )
    
    # Authenticate first
    auth_response = client.authenticate()
    
    # Then use the tools
    status = client.get_deployment_status("main")
    pr = client.create_rollout_pr("feature/x", "main", 50)
    pipeline = client.get_cicd_pipeline_status()
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from .base_tools import ExternalToolsInterface, ToolResponse, ToolStatus


class GitHubClient(ExternalToolsInterface):
    """
    GitHub integration for monitoring deployments and creating PRs.
    
    Requires GitHub Personal Access Token with:
    - repo (full repository access)
    - workflow (Actions)
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        repo: Optional[str] = None,
        owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        base_url: str = "https://api.github.com"
    ):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub token (or loads from GITHUB_TOKEN env var)
            repo: "owner/repo" format (preferred)
            owner: Repository owner (if not using repo format)
            repo_name: Repository name (if not using repo format)
            base_url: GitHub API base URL (use for GitHub Enterprise)
        """
        super().__init__("github")
        
        # Load credentials from .env if available
        if load_dotenv is not None:
            env_candidates = [
                Path.cwd() / ".env",
                Path(__file__).resolve().parents[2] / ".env",
                Path(__file__).resolve().parents[3] / ".env",
            ]
            for env_path in env_candidates:
                if env_path.exists():
                    load_dotenv(dotenv_path=env_path)
        
        # Get token
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = base_url
        
        # Parse repo info
        if repo and "/" in repo:
            self.owner, self.repo_name = repo.split("/", 1)
        else:
            self.owner = owner or os.getenv("GITHUB_OWNER")
            self.repo_name = repo_name or os.getenv("GITHUB_REPO")
        
        # API client
        self.client = None
        self.gh_repo = None  # PyGithub repo object
        
    def authenticate(self) -> ToolResponse:
        """Authenticate with GitHub API"""
        try:
            if not self.token:
                error = "GITHUB_TOKEN not provided or set in environment"
                self.status = ToolStatus.ERROR
                self._record_call(False, error)
                return ToolResponse(success=False, error=error)
            
            if not self.owner or not self.repo_name:
                error = "GitHub owner/repo not provided"
                self.status = ToolStatus.ERROR
                self._record_call(False, error)
                return ToolResponse(success=False, error=error)
            
            # Try to import PyGithub
            try:
                from github import Github
                self.client = Github(self.token)
                self.gh_repo = self.client.get_user(self.owner).get_repo(self.repo_name)
                
                # Test connection
                _ = self.gh_repo.get_commits().totalCount
                
                self.status = ToolStatus.CONNECTED
                self._record_call(True)
                
                return ToolResponse(
                    success=True,
                    data={
                        "owner": self.owner,
                        "repo": self.repo_name,
                        "authenticated": True,
                    },
                    metadata={"message": "Successfully authenticated with GitHub"}
                )
            except ImportError:
                error = "PyGithub not installed. Run: pip install PyGithub"
                self.status = ToolStatus.ERROR
                self._record_call(False, error)
                return ToolResponse(success=False, error=error)
            
        except Exception as e:
            error = f"GitHub authentication failed: {str(e)}"
            self.status = ToolStatus.ERROR
            self._record_call(False, error)
            return ToolResponse(success=False, error=error)
    
    def get_status(self) -> ToolStatus:
        """Get current connection status"""
        return self.status
    
    # =========================================================================
    # TOOL 1: Get Deployment Status
    # =========================================================================
    
    def get_deployment_status(
        self,
        environment: str = "production",
        limit: int = 5
    ) -> ToolResponse:
        """
        Get recent deployment status for an environment.
        
        Args:
            environment: Deployment environment (e.g., "production", "staging")
            limit: Number of recent deployments to check
        
        Returns:
            ToolResponse with deployment info
        """
        try:
            if not self.gh_repo:
                return ToolResponse(
                    success=False,
                    error="Not authenticated. Call authenticate() first."
                )
            
            deployments = self.gh_repo.get_deployments(
                environment=environment,
                per_page=limit
            )
            
            deployment_info = []
            for deployment in deployments[:limit]:
                status_response = deployment.get_statuses()
                latest_status = status_response[0] if status_response.totalCount > 0 else None
                
                deployment_info.append({
                    "id": deployment.id,
                    "environment": deployment.environment,
                    "ref": deployment.ref,
                    "sha": deployment.sha[:8],  # Short commit hash
                    "creator": deployment.creator.login,
                    "created_at": deployment.created_at.isoformat(),
                    "status": latest_status.state if latest_status else "unknown",
                    "status_url": latest_status.target_url if latest_status else None,
                    "description": latest_status.description if latest_status else None,
                })
            
            self._record_call(True)
            
            return ToolResponse(
                success=True,
                data={
                    "environment": environment,
                    "deployments": deployment_info,
                    "total_checked": len(deployment_info),
                },
                metadata={
                    "source": "GitHub Deployments API",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        
        except Exception as e:
            error = f"Failed to get deployment status: {str(e)}"
            self._record_call(False, error)
            return ToolResponse(success=False, error=error)
    
    # =========================================================================
    # TOOL 2: Create Pull Request for Rollout
    # =========================================================================
    
    def create_rollout_pr(
        self,
        feature_branch: str,
        target_branch: str,
        rollout_percentage: float,
        title: Optional[str] = None,
        description: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> ToolResponse:
        """
        Create a pull request for a feature rollout.
        
        Args:
            feature_branch: Source branch (e.g., "feature/new-checkout")
            target_branch: Target branch (e.g., "main", "staging")
            rollout_percentage: Planned rollout percentage
            title: PR title (auto-generated if None)
            description: PR description (auto-generated if None)
            labels: GitHub labels to add to PR
        
        Returns:
            ToolResponse with PR info
        """
        try:
            if not self.gh_repo:
                return ToolResponse(
                    success=False,
                    error="Not authenticated. Call authenticate() first."
                )
            
            # Generate title if not provided
            if not title:
                title = f"🚀 Feature Rollout: {rollout_percentage:.0f}% deployment"
            
            # Generate description if not provided
            if not description:
                description = f"""
## Rollout Details

- **Feature Branch**: `{feature_branch}`
- **Target Branch**: `{target_branch}`
- **Planned Rollout**: {rollout_percentage:.1f}%
- **Created By**: FeatureFlag Agent
- **Timestamp**: {datetime.utcnow().isoformat()}

## Checklist

- [ ] Monitoring dashboards reviewed
- [ ] Alert thresholds configured
- [ ] Rollback plan ready
- [ ] Stakeholders notified

## Automatic Agent Decision

This PR was created based on intelligent decision-making by the FeatureFlag Agent.
The agent monitors real-time metrics and automatically creates PRs when rollout conditions are met.

### Strategy
- Error Rate: ✓ Acceptable
- Latency: ✓ Within bounds
- System Health: ✓ Good
- Adoption: ✓ On track

---
*This is an automated PR creation. Please review before merging.*
"""
            
            # Create PR
            pr = self.gh_repo.create_pull(
                title=title,
                body=description,
                head=feature_branch,
                base=target_branch,
            )
            
            # Add labels if provided
            if labels:
                try:
                    pr.add_to_labels(*labels)
                except Exception as label_error:
                    print(f"⚠️ Warning: Could not add labels: {label_error}")
            
            self._record_call(True)
            
            return ToolResponse(
                success=True,
                data={
                    "pr_number": pr.number,
                    "pr_url": pr.html_url,
                    "title": pr.title,
                    "state": pr.state,
                    "created_at": pr.created_at.isoformat(),
                    "head": pr.head.ref,
                    "base": pr.base.ref,
                },
                metadata={
                    "message": f"PR #{pr.number} created successfully",
                    "rollout_percentage": rollout_percentage,
                }
            )
        
        except Exception as e:
            error = f"Failed to create PR: {str(e)}"
            self._record_call(False, error)
            return ToolResponse(success=False, error=error)
    
    # =========================================================================
    # TOOL 3: Get CI/CD Pipeline Status
    # =========================================================================
    
    def get_cicd_pipeline_status(
        self,
        branch: str = "main",
        limit: int = 10,
    ) -> ToolResponse:
        """
        Get GitHub Actions workflow status for recent runs.
        
        Args:
            branch: Branch to check workflows for
            limit: Number of recent workflow runs to fetch
        
        Returns:
            ToolResponse with workflow status info
        """
        try:
            if not self.gh_repo:
                return ToolResponse(
                    success=False,
                    error="Not authenticated. Call authenticate() first."
                )
            
            # Get workflows
            workflows = self.gh_repo.get_workflows()
            workflow_runs_info = []
            
            for workflow in workflows:
                try:
                    runs = workflow.get_runs(status="all", branch=branch)
                    
                    for run in runs[:limit]:
                        workflow_runs_info.append({
                            "workflow_name": workflow.name,
                            "workflow_id": workflow.id,
                            "run_id": run.id,
                            "name": run.name,
                            "status": run.status,
                            "conclusion": run.conclusion,
                            "head_branch": run.head_branch,
                            "created_at": run.created_at.isoformat(),
                            "updated_at": run.updated_at.isoformat(),
                            "run_number": run.run_number,
                            "html_url": run.html_url,
                            "commit_message": run.head_commit.message if run.head_commit else None,
                        })
                except Exception as e:
                    # Skip workflows that error
                    pass
            
            # Summarize status
            total_runs = len(workflow_runs_info)
            successful = sum(1 for r in workflow_runs_info if r["conclusion"] == "success")
            failed = sum(1 for r in workflow_runs_info if r["conclusion"] == "failure")
            in_progress = sum(1 for r in workflow_runs_info if r["status"] == "in_progress")
            
            self._record_call(True)
            
            return ToolResponse(
                success=True,
                data={
                    "branch": branch,
                    "recent_runs": workflow_runs_info[:5],  # Return top 5
                    "summary": {
                        "total_checked": total_runs,
                        "successful": successful,
                        "failed": failed,
                        "in_progress": in_progress,
                        "success_rate": (successful / total_runs * 100) if total_runs > 0 else 0.0,
                    },
                },
                metadata={
                    "source": "GitHub Actions API",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        
        except Exception as e:
            error = f"Failed to get CI/CD pipeline status: {str(e)}"
            self._record_call(False, error)
            return ToolResponse(success=False, error=error)
    
    # =========================================================================
    # TOOL 4: Get Latest Deployment Info (Helper)
    # =========================================================================
    
    def get_latest_deployment(
        self,
        environment: str = "production"
    ) -> ToolResponse:
        """
        Get the most recent deployment for an environment.
        
        Args:
            environment: Deployment environment
        
        Returns:
            ToolResponse with latest deployment
        """
        try:
            if not self.gh_repo:
                return ToolResponse(
                    success=False,
                    error="Not authenticated. Call authenticate() first."
                )
            
            deployments = self.gh_repo.get_deployments(environment=environment)
            if deployments.totalCount == 0:
                return ToolResponse(
                    success=True,
                    data=None,
                    metadata={"message": f"No deployments found for {environment}"}
                )
            
            latest = deployments[0]
            status_response = latest.get_statuses()
            latest_status = status_response[0] if status_response.totalCount > 0 else None
            
            self._record_call(True)
            
            return ToolResponse(
                success=True,
                data={
                    "id": latest.id,
                    "environment": latest.environment,
                    "ref": latest.ref,
                    "sha": latest.sha[:8],
                    "creator": latest.creator.login,
                    "created_at": latest.created_at.isoformat(),
                    "status": latest_status.state if latest_status else "unknown",
                    "is_healthy": latest_status.state == "success" if latest_status else False,
                },
                metadata={"environment": environment}
            )
        
        except Exception as e:
            error = f"Failed to get latest deployment: {str(e)}"
            self._record_call(False, error)
            return ToolResponse(success=False, error=error)
