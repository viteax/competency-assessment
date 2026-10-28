"""Копии вне сервера: deploy/offsite.sh и deploy/setup-offsite.sh с заглушками rclone и docker."""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"
HC = "https://hc.example/abc"

STUBS = {
    "rclone": """#!/bin/sh
echo "rclone $*" >> "$LOG"
case "$1" in
listremotes) [ -z "${CONFIGURED:-}" ] || echo "offsite:" ;;
copy) exit "${COPY_RC:-0}" ;;
cat) cat "$REMOTE_FILE" ;;
esac
""",
    "wget": """#!/bin/sh
echo "wget $*" >> "$LOG"
[ -z "${VK_ANSWER:-}" ] || echo "$VK_ANSWER"
""",
    # docker compose ... для setup-offsite.sh: rclone obscure и проверка копии
    "docker": """#!/bin/sh
echo "docker $*" >> "$LOG"
case "$*" in
*"obscure -"*) cat > /dev/null; echo OBSCURED ;;
*--check*) echo "проверка пройдена" ;;
esac
""",
}


@pytest.fixture
def env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in STUBS.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    (tmp_path / "backups").mkdir()
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "LOG": str(tmp_path / "log"),
        "BACKUP_DIR": str(tmp_path / "backups"),
        "OFFSITE_STATE": str(tmp_path / "state"),
        "HEALTHCHECK_URL": HC,
    }


def offsite(env, *args, **extra):
    Path(env["LOG"]).write_text("")
    result = subprocess.run(
        ["sh", str(DEPLOY / "offsite.sh"), *args],
        capture_output=True,
        text=True,
        timeout=10,
        env={**env, **extra},
    )
    return result, Path(env["LOG"]).read_text().splitlines()


def dump(env, stamp, hours_ago=1):
    path = Path(env["BACKUP_DIR"]) / f"competency-{stamp}.dump"
    path.write_bytes(f"dump {stamp}".encode())
    moment = time.time() - hours_ago * 3600
    os.utime(path, (moment, moment))
    return path


def uploads(calls):
    return [call for call in calls if call.startswith("rclone copy")]


def test_new_copy_goes_to_storage_once_and_reports(env):
    dump(env, "2026-10-27_0330")
    result, calls = offsite(env, "--once", CONFIGURED="1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert uploads(calls)
    assert any("rclone delete" in call and "--min-age 90d" in call for call in calls)
    assert calls[-1].startswith("wget") and calls[-1].endswith(HC)

    result, calls = offsite(env, "--once", CONFIGURED="1")
    assert result.returncode == 0
    assert not uploads(calls)  # новых копий нет – хранилище не трогаем
    assert calls[-1].endswith(HC)


def test_stale_backup_is_reported_as_failure(env):
    dump(env, "2026-10-25_0330", hours_ago=30)
    result, calls = offsite(env, "--once", CONFIGURED="1")
    assert result.returncode == 1
    assert not uploads(calls)
    assert calls[-1].endswith(f"{HC}/fail")


def test_failed_upload_is_silent_and_retried(env):
    dump(env, "2026-10-27_0330")
    result, calls = offsite(env, "--once", CONFIGURED="1", COPY_RC="1")
    assert result.returncode == 1
    # Без сигнала: мониторинг напишет сам, если отправка не удается дольше суток.
    assert not any(call.startswith("wget") for call in calls)

    result, calls = offsite(env, "--once", CONFIGURED="1")
    assert result.returncode == 0 and uploads(calls)


def test_without_storage_only_watches_backups(env):
    dump(env, "2026-10-27_0330")
    result, calls = offsite(env, "--once")
    assert result.returncode == 0
    assert not uploads(calls)
    assert "только на сервере" in calls[-1]

    result, calls = offsite(env, "--once", HEALTHCHECK_URL="")
    assert result.returncode == 0
    assert not any(call.startswith("wget") for call in calls)


def test_vk_reports_ok_once_a_day_and_failure_at_once(env):
    vk = {"HEALTHCHECK_URL": "", "NOTIFY_VK_TOKEN": "TOKEN", "NOTIFY_VK_USER_ID": "42"}

    def sent(calls):
        return [c for c in calls if "api.vk.com" in c]

    stale = dump(env, "2026-10-25_0330", hours_ago=30)
    result, calls = offsite(env, "--once", CONFIGURED="1", **vk)
    assert result.returncode == 1
    [message] = sent(calls)
    assert "user_id=42" in message and "access_token=TOKEN" in message
    assert "Сбой копий базы" in message and "%0A" in message  # многострочный текст закодирован
    _, calls = offsite(env, "--once", CONFIGURED="1", **vk)
    assert not sent(calls)  # тот же сбой через час – без повтора

    stale.unlink()
    dump(env, "2026-10-27_0330")
    _, calls = offsite(env, "--once", CONFIGURED="1", **vk)
    assert len(sent(calls)) == 1 and "в порядке" in sent(calls)[0]
    _, calls = offsite(env, "--once", CONFIGURED="1", **vk)
    assert not sent(calls)  # «в порядке» – раз в день

    Path(env["OFFSITE_STATE"] + ".vk-ok").unlink()
    result, calls = offsite(
        env, "--once", CONFIGURED="1", VK_ANSWER='{"error":{"error_code":5}}', **vk
    )
    assert result.returncode == 0  # отказ VK не мешает копиям, но виден в логе
    assert "VK отказал" in result.stdout
    assert not Path(env["OFFSITE_STATE"] + ".vk-ok").exists()  # не отмечено – повторим через час


def test_check_compares_copy_downloaded_from_storage(env, tmp_path):
    path = dump(env, "2026-10-27_0330")
    result, _ = offsite(env, "--check", CONFIGURED="1", REMOTE_FILE=str(path))
    assert result.returncode == 0 and "проверка пройдена" in result.stdout

    broken = tmp_path / "broken"
    broken.write_bytes(b"other")
    result, _ = offsite(env, "--check", CONFIGURED="1", REMOTE_FILE=str(broken))
    assert result.returncode == 1 and "не совпадает" in result.stderr


@pytest.fixture
def server(tmp_path):
    """Копия прода: скрипт настройки и .env."""
    root = tmp_path / "opt"
    (root / "deploy").mkdir(parents=True)
    shutil.copy(DEPLOY / "setup-offsite.sh", root / "deploy")
    (root / ".env").write_text("SECRET_KEY=x\nHEALTHCHECK_URL=https://old.example\n")
    return root


def setup(env, server, answers, mode="yandex"):
    Path(env["LOG"]).write_text("")
    return subprocess.run(
        ["sh", str(server / "deploy" / "setup-offsite.sh"), mode],
        input=answers,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def test_setup_writes_encrypted_storage_and_monitoring(env, server):
    hc = "https://hc-ping.com/uuid"
    result = setup(env, server, f"my-backups\nKEYID\nSECRET\n{hc}\n")
    assert result.returncode == 0, result.stdout + result.stderr

    conf = (server / "deploy" / "rclone" / "rclone.conf").read_text()
    assert "access_key_id = KEYID\nsecret_access_key = SECRET" in conf
    assert "remote = store:my-backups/competency\npassword = OBSCURED" in conf
    assert conf in result.stdout  # настройку показали, чтобы сохранить вне сервера
    assert oct((server / "deploy" / "rclone" / "rclone.conf").stat().st_mode & 0o777) == "0o600"
    assert (server / ".env").read_text() == f"SECRET_KEY=x\nHEALTHCHECK_URL={hc}\n"

    calls = Path(env["LOG"]).read_text()
    assert "backup.sh" in calls and "--check" in calls and "up -d --force-recreate offsite" in calls

    again = setup(env, server, f"my-backups\nKEYID\nSECRET\n{hc}\n")
    assert again.returncode == 1 and "уже настроено" in again.stderr


def test_setup_rejects_bad_answers(env, server):
    result = setup(env, server, "My Bucket\n")
    assert result.returncode == 1 and "имя бакета" in result.stderr
    result = setup(env, server, "my-backups\nKEYID\nSECRET\nhttp://hc\n")
    assert result.returncode == 1 and "https://" in result.stderr
    assert not (server / "deploy" / "rclone" / "rclone.conf").exists()
