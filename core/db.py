"""
core/db.py — SQLite 数据库管理

管理元数据存储:
  - rule_template: 保存的规则模板
  - scan_job: 扫描任务记录
  - trade: 交易明细
  - trade_feature: 入场时的因子快照

用法:
    from core.db import init_db, get_connection
    init_db("data/factorlab.db")
    conn = get_connection("data/factorlab.db")
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS rule_template (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    config      TEXT NOT NULL,
    created     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scan_job (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_json   TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    interval    TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    created     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_job_id   INTEGER REFERENCES scan_job(id),
    direction     TEXT NOT NULL,
    entry_time    TEXT NOT NULL,
    entry_price   REAL NOT NULL,
    exit_time     TEXT NOT NULL,
    exit_price    REAL NOT NULL,
    sl_price      REAL NOT NULL,
    tp_price      REAL NOT NULL,
    result        TEXT NOT NULL,
    r_multiple    REAL NOT NULL,
    holding_bars  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_feature (
    trade_id     INTEGER REFERENCES trade(id),
    feature_name TEXT NOT NULL,
    value        REAL NOT NULL,
    PRIMARY KEY (trade_id, feature_name)
);

CREATE INDEX IF NOT EXISTS idx_scan_job_created ON scan_job(created);
CREATE INDEX IF NOT EXISTS idx_trade_scan_job ON trade(scan_job_id);
"""


def init_db(db_path: str | Path = "data/factorlab.db") -> Path:
    """
    初始化数据库，创建所有表（幂等）。

    Args:
        db_path: 数据库文件路径，默认为 data/factorlab.db

    Returns:
        数据库文件的绝对路径
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    return db_path.resolve()


def get_connection(db_path: str | Path = "data/factorlab.db") -> sqlite3.Connection:
    """
    获取数据库连接。

    Args:
        db_path: 数据库文件路径

    Returns:
        sqlite3.Connection 对象，启用 WAL 模式和 foreign keys
    """
    db_path = Path(db_path)
    if not db_path.exists():
        init_db(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn
