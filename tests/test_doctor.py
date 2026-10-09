from priorwork import scaffold
from priorwork.doctor import NG, OK, WARN, run_checks


def by_name(checks):
    return {name: (level, msg) for level, name, msg in checks}


def test_fresh_workspace_is_healthy_apart_from_missing_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.delenv("S2_API_KEY", raising=False)
    scaffold.init(tmp_path)
    checks = by_name(run_checks(tmp_path))
    assert checks["構成"][0] == OK and checks["AGENTS.md・スキル"][0] == OK and checks["エンジンの版"][0] == OK
    assert checks[".env"][0] == WARN and checks["Semantic Scholar"][0] == WARN
    assert checks["Git"][0] == WARN and "リモート" in checks["Git"][1]
    assert not any(level == NG for level, _ in checks.values())


def test_missing_directories_and_version_drift_are_reported(tmp_path):
    (tmp_path / "requirements.txt").write_text("priorwork==0.0.1\n")
    checks = by_name(run_checks(tmp_path))
    assert checks["構成"][0] == WARN and "priorwork init" in checks["構成"][1]
    assert checks["エンジンの版"][0] == WARN and "0.0.1" in checks["エンジンの版"][1]


def test_online_failures_are_reported_not_raised(tmp_path):
    class Client:
        def search(self, *a, **k):
            raise RuntimeError("HTTP 429")

        def openalex_works(self, *a, **k):
            return [{"doi": "x"}]

    scaffold.init(tmp_path)
    checks = by_name(run_checks(tmp_path, Client()))
    assert checks["Semantic Scholar 接続"] == (NG, "HTTP 429") and checks["OpenAlex 接続"][0] == OK


def test_git_checks_github_remote_and_tracked_env(tmp_path):
    import subprocess
    scaffold.init(tmp_path)
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("remote", "add", "origin", "git@github.com:someone/my-surveys.git")
    checks = by_name(run_checks(tmp_path))
    assert checks["Git"][0] == OK and ".env の管理" not in checks

    (tmp_path / ".env").write_text("SEMANTIC_SCHOLAR_API_KEY=secret")
    git("add", "-f", ".env")
    assert by_name(run_checks(tmp_path))[".env の管理"][0] == NG


def test_not_a_git_repo_is_a_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold, "git_init", lambda root: False)
    scaffold.init(tmp_path)
    assert by_name(run_checks(tmp_path))["Git"][0] == WARN
