from gway_webos_tv import github_prs


def test_github_pr_summary(monkeypatch):
    class Result:
        stdout = '[{"number":42,"title":"Fix CI","isDraft":false,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}]}]'
    monkeypatch.setattr(github_prs.subprocess, 'run', lambda *args, **kwargs: Result())
    github_prs._cache = None
    result = github_prs.snapshot()
    assert result['pull_requests'][0]['ci'] == 'passed'
    assert result['pull_requests'][0]['repo'] == github_prs.REPOS[0]
    assert len(result['pull_requests']) == len(github_prs.REPOS)
