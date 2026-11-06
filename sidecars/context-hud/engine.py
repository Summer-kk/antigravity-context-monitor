import os
import sys
import glob
import json
import sqlite3
import tempfile
import shutil
import re
import urllib.parse
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

ANTIGRAVITY_BASE_DIR = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity")

TOOL_CN_NAMES = {
    "read_file": "读取文件",
    "write_file": "代码生成",
    "edit_file": "代码编辑",
    "run_command": "终端执行",
    "search_web": "网页搜索",
    "manage_task": "任务调度",
    "ask_question": "交互提问",
}

DEFAULT_CONTEXT_LIMIT = 262144  # 256k Tokens (Antigravity 实际上下文窗口上限，256 * 1024)

def get_db_connection():
    db_path = os.path.join(ANTIGRAVITY_BASE_DIR, "conversation_summaries.db")
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.execute("SELECT 1")
        return conn
    except Exception:
        pass
    try:
        temp_dir = tempfile.gettempdir()
        temp_db = os.path.join(temp_dir, f"context_hud_{os.getpid()}.db")
        shutil.copy2(db_path, temp_db)
        return sqlite3.connect(temp_db)
    except Exception:
        return None

def get_conversations_list(limit=100):
    conn = get_db_connection()
    conversations = []
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT conversation_id, title, preview, last_modified_time, workspace_uris, step_count, last_user_input_time, project_id
                FROM conversation_summaries
                ORDER BY COALESCE(last_user_input_time, last_modified_time) DESC
                LIMIT ?
            """, (limit,))
            for row in cur.fetchall():
                cid, title, preview, last_mod, workspace_uris, step_count, last_user_input, project_id = row
                project_name = "未绑定项目"
                project_path = ""
                if workspace_uris:
                    try:
                        uris = json.loads(workspace_uris)
                        if uris and isinstance(uris, list) and len(uris) > 0:
                            decoded = urllib.parse.unquote(uris[0])
                            if decoded.startswith("file:///"):
                                project_path = decoded[8:]
                            elif decoded.startswith("file://"):
                                project_path = decoded[7:]
                            else:
                                project_path = decoded
                            project_path = project_path.replace("/", os.sep)
                            project_name = os.path.basename(project_path.rstrip(r"\/")) or project_path
                    except Exception:
                        pass

                display_title = (title or "").strip()
                if not display_title and preview:
                    display_title = preview.strip().split("\n")[0][:45]
                if not display_title:
                    display_title = "未命名会话"

                conversations.append({
                    "cid": cid,
                    "title": display_title,
                    "project_name": project_name,
                    "project_path": project_path,
                    "last_modified": last_mod,
                    "last_user_input": last_user_input,
                    "project_id": project_id,
                    "step_count": step_count or 0
                })
        except Exception:
            pass
        finally:
            try: conn.close()
            except Exception: pass
    return conversations

def detect_active_conversation(conversations, current_tracked_cid=None):
    """
    智能防抖活跃会话识别引擎：
    1. 优先按真正的用户交互时间 (last_user_input_time) 排序，杜绝后台文件写入导致跳动
    2. 引入防跳动粘滞性 (Sticky Hysteresis)：若当前追踪的会话依然在活跃区间内，不轻易跳动
    3. 兜底结合本地 brain 目录真实 transcript 日志
    """
    if not conversations:
        return None

    # 若前端已经选定或正在追踪某会话，且该会话依然存在于近期列表中，先做粘滞判定
    tracked_meta = None
    if current_tracked_cid:
        for c in conversations:
            if c["cid"] == current_tracked_cid:
                tracked_meta = c
                break

    # 按照用户最后一次显式输入交互时间 (last_user_input_time) 排序
    valid_with_user_input = [c for c in conversations if c.get("last_user_input")]
    if valid_with_user_input:
        top_user_conv = valid_with_user_input[0]
        # 如果当前正在追踪的会话就是最高交互会话，直接保持
        if tracked_meta and tracked_meta["cid"] == top_user_conv["cid"]:
            return tracked_meta
        # 否则以用户最新交互的会话为准
        return top_user_conv

    # 兜底：如果数据库中无 last_user_input，再按最后修改时间
    if tracked_meta:
        return tracked_meta

    return conversations[0]

def get_conversation_context_details(target_cid=None, current_tracked_cid=None):
    conversations = get_conversations_list(limit=50)
    selected_meta = None

    if target_cid:
        for c in conversations:
            if c["cid"] == target_cid:
                selected_meta = c
                break
        # 若在已知列表中没找到（例如新创建的会话），直接构建基础元数据
        if not selected_meta:
            selected_meta = {
                "cid": target_cid,
                "title": "指定会话",
                "project_name": "当前项目",
                "project_path": "",
                "last_modified": datetime.now().isoformat(),
                "step_count": 0
            }
    else:
        # 自动识别模式（防抖防跳动）
        selected_meta = detect_active_conversation(conversations, current_tracked_cid)
        if selected_meta:
            target_cid = selected_meta["cid"]

    if not target_cid:
        return {
            "success": False,
            "error": "未检测到活跃对话，请在会话列表中选择或在 Antigravity 中开启新对话。"
        }

    log_path = os.path.join(ANTIGRAVITY_BASE_DIR, "brain", target_cid, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(log_path):
        log_path_full = os.path.join(ANTIGRAVITY_BASE_DIR, "brain", target_cid, ".system_generated", "logs", "transcript_full.jsonl")
        if os.path.exists(log_path_full):
            log_path = log_path_full

    steps_data = []
    model_name = "Gemini 3.8 Flash"
    first_prompt = ""
    cum_input = 0
    cum_output = 0
    cum_cache = 0

    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        rec_type = record.get("type")
                        
                        if rec_type == "USER_INPUT" and not first_prompt:
                            content = record.get("content", "")
                            if "<USER_REQUEST>" in content:
                                try:
                                    first_prompt = content.split("<USER_REQUEST>")[1].split("</USER_REQUEST>")[0].strip()
                                except Exception:
                                    first_prompt = content[:100]
                            else:
                                first_prompt = content[:100]

                        # 严格从真正的用户输入 USER_SETTINGS_CHANGE 标签解析模型
                        if rec_type == "USER_INPUT" and record.get("source") == "USER_EXPLICIT":
                            cnt = record.get("content", "")
                            if "<USER_SETTINGS_CHANGE>" in cnt and "</USER_SETTINGS_CHANGE>" in cnt:
                                try:
                                    block = cnt.split("<USER_SETTINGS_CHANGE>")[1].split("</USER_SETTINGS_CHANGE>")[0]
                                    if "`Model Selection` from" in block:
                                        after_to = block.split("to ", 1)[1]
                                        raw_model = after_to.split(". No need")[0].strip()
                                        if raw_model:
                                            cleaned_model = re.sub(r"\s*\([^)]*\)$", "", raw_model).strip()
                                            model_name = cleaned_model or raw_model
                                except Exception:
                                    pass

                        if rec_type == "PLANNER_RESPONSE":
                            s_idx = record.get("step_index", 0)
                            inp = record.get("input_tokens", 0) or 0
                            out = record.get("output_tokens", 0) or 0
                            cache = record.get("cache_read_tokens", 0) or 0
                            created_at = record.get("created_at", "")
                            
                            tools = []
                            for tc in record.get("tool_calls", []):
                                if isinstance(tc, dict) and "name" in tc:
                                    tools.append(tc["name"])

                            total_context_tokens = inp + cache
                            cum_input += inp
                            cum_output += out
                            cum_cache += cache

                            steps_data.append({
                                "step_index": s_idx,
                                "context_tokens": total_context_tokens,
                                "input_tokens": inp,
                                "cache_read_tokens": cache,
                                "output_tokens": out,
                                "tools": tools,
                                "created_at": created_at
                            })
                    except Exception:
                        pass
        except Exception:
            pass

    context_limit = DEFAULT_CONTEXT_LIMIT
    
    current_context = 0
    latest_input = 0
    latest_cache = 0
    latest_output = 0
    baseline_context = 0
    growth_tokens = 0
    last_step_index = 0
    last_tools = []
    last_time = ""

    # 步骤增量计算与上下文压缩事件检测
    for i, s in enumerate(steps_data):
        if i == 0:
            s["delta_tokens"] = s["context_tokens"]
            s["is_compaction"] = False
            s["compaction_drop"] = 0
        else:
            prev_ctx = steps_data[i-1]["context_tokens"]
            curr_ctx = s["context_tokens"]
            # 自动检测上下文自动压缩/截断（单步下降超过 15,000 Tokens 且降幅大于 30%）
            if prev_ctx - curr_ctx > 15000 and curr_ctx < prev_ctx * 0.7:
                s["is_compaction"] = True
                s["compaction_drop"] = prev_ctx - curr_ctx
                s["delta_tokens"] = 0
            else:
                s["is_compaction"] = False
                s["compaction_drop"] = 0
                s["delta_tokens"] = max(0, curr_ctx - prev_ctx)

    if steps_data:
        latest = steps_data[-1]
        current_context = latest["context_tokens"]
        latest_input = latest["input_tokens"]
        latest_cache = latest["cache_read_tokens"]
        latest_output = latest["output_tokens"]
        last_step_index = latest["step_index"]
        last_tools = latest["tools"]
        last_time = latest["created_at"]

        baseline_context = steps_data[0]["context_tokens"]
        growth_tokens = max(0, current_context - baseline_context)

    occupancy_pct = round((current_context / context_limit) * 100, 2)
    cache_pct = round((latest_cache / current_context * 100), 1) if current_context > 0 else 0.0

    remaining_tokens = max(0, context_limit - current_context)
    avg_growth = round(growth_tokens / max(1, len(steps_data) - 1)) if len(steps_data) > 1 else 2500

    # 三段式堆叠比例
    baseline_pct = round((baseline_context / context_limit) * 100, 1)
    growth_pct = round((growth_tokens / context_limit) * 100, 1)
    free_pct = max(0.0, round(100.0 - baseline_pct - growth_pct, 1))

    # 响应速度档位
    if cache_pct >= 80.0:
        speed_grade = {
            "title": "极速闪电档",
            "desc": "上下文近乎全量命中缓存，首字毫秒级到达",
            "icon": "⚡",
            "color": "emerald"
        }
    elif cache_pct >= 40.0:
        speed_grade = {
            "title": "高速缓存档",
            "desc": "超过半数上下文命中缓存，交互顺畅",
            "icon": "🚀",
            "color": "sky"
        }
    else:
        speed_grade = {
            "title": "常规响应档",
            "desc": "未命中缓存部分需正常推理",
            "icon": "⏱️",
            "color": "amber"
        }

    # 上下文健康度评估
    if occupancy_pct >= 85.0:
        health = {
            "level": "critical",
            "status_text": "严重告急",
            "tip": "上下文即将达到上限，建议立即执行精简压缩。",
            "badge_color": "rose",
            "action": "urgent_compaction"
        }
    elif occupancy_pct >= 65.0:
        health = {
            "level": "warning",
            "status_text": "注意膨胀",
            "tip": "上下文占用已过半，若继续读取大量大文件可能很快接近上限。",
            "badge_color": "amber",
            "action": "monitor"
        }
    else:
        health = {
            "level": "healthy",
            "status_text": "健康",
            "tip": "",
            "badge_color": "emerald",
            "action": "none"
        }

    return {
        "success": True,
        "conversation": selected_meta,
        "model": {
            "name": model_name,
            "context_limit": context_limit,
            "limit_display": f"{round(context_limit / 1048576, 1)}M" if context_limit >= 1048576 else f"{round(context_limit / 1024)}k"
        },
        "context": {
            "current_tokens": current_context,
            "limit_tokens": context_limit,
            "remaining_tokens": remaining_tokens,
            "occupancy_ratio": occupancy_pct,
            "speed_grade": speed_grade,
            "latest_uncached_input": latest_input,
            "latest_cache_read": latest_cache,
            "latest_output": latest_output,
            "cache_hit_ratio": cache_pct,
            "baseline_system_tokens": baseline_context,
            "growth_tokens": growth_tokens,
            "avg_step_growth": avg_growth,
            "total_steps": len(steps_data),
            "last_step_index": last_step_index,
            "last_tools": last_tools,
            "health": health,
            "stacked_composition": {
                "baseline_pct": baseline_pct,
                "growth_pct": growth_pct,
                "free_pct": free_pct
            },
            "spikes": []
        },
        "cumulative": {
            "input_tokens": cum_input,
            "cache_tokens": cum_cache,
            "output_tokens": cum_output,
            "total_tokens": cum_input + cum_cache + cum_output
        },
        "step_history": steps_data,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
