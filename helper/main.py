import os
import re
import sys
import subprocess
from datetime import datetime, timedelta

# ====================== 配置 ======================
MAGZINES = {
    "ny": {
        "id": "ny",
        "name": "The New Yorker Magazine",
        "recipe": "The New Yorker Magazine",
        "folder": "the_new_yorker",
        "date_regex": r"magazine/\K\d{4}/\d{2}/\d{2}",
    },
    "te": {
        "id": "te",
        "name": "The Economist",
        "recipe": "The Economist.recipe",  # ← 关键修改：使用仓库中的文件
        "folder": "the_economist",
        "date_regex": r"images/\K(\d{8})",
    },
    "tm": {
        "id": "tm",
        "name": "TIME Magazine",
        "recipe": "TIME Magazine",
        "folder": "time_magzine",
        "date_regex": r"TIM\K(\d{6})",
    }
}

RECIPE_OPTIONS = {
    "te": "date",
    "ny": "date",
    "tm": "edition",
}

BOOKS_DIR = "converted_ebooks"


def safe_strptime(date_str):
    """增强日期解析，增加容错"""
    if not date_str:
        return None
    clean = re.sub(r'[^0-9]', '', date_str)
    for length in [8, 6]:
        try:
            return datetime.strptime(clean[:length], "%Y%m%d"[:length])
        except:
            continue
    return None


def run_command(args):
    """执行命令并实时输出"""
    print(f"Running: {' '.join(args)}")
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                               text=True, env=env)
    full_output = []
    for line in process.stdout:
        print(line, end="")
        full_output.append(line)
    process.wait()
    return "".join(full_output), process.returncode


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <mag_id> [issue_date]")
        sys.exit(1)

    mag_id = sys.argv[1]
    if mag_id not in MAGZINES:
        print(f"Unknown magazine: {mag_id}")
        sys.exit(1)

    issue_date = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] and sys.argv[2] != "." else None

    # ==================== 日期调整 ====================
    if (mag_id in ["te", "ny"]) and issue_date:
        try:
            dt_obj = safe_strptime(issue_date)
            if dt_obj:
                if mag_id == "te":
                    offset = (dt_obj.weekday() + 2) % 7
                    target_fmt = "%Y-%m-%d"
                else:
                    offset = dt_obj.weekday()
                    target_fmt = "%Y/%m/%d"

                if offset > 0:
                    dt_obj = dt_obj - timedelta(days=offset)
                    issue_date = dt_obj.strftime(target_fmt)
                    print(f"Adjusted date for {mag_id}: {issue_date}")
        except Exception as e:
            print(f"Warning: Date adjustment failed: {e}")

    config = MAGZINES[mag_id]
    recipe = config["recipe"]

    if not os.path.exists(BOOKS_DIR):
        os.makedirs(BOOKS_DIR)

    # IP 检查（调试用）
    try:
        ip_info = subprocess.check_output(["curl", "-s", "https://ifconfig.me"], text=True).strip()
        print(f"Current Public IP: {ip_info}")
    except:
        pass

    print(f"--- Fetching {config['name']} ---")
    raw_epub = "temp_output.epub"

    # ===== 关键修改：直接使用配置中的 recipe 路径 =====
    # recipe 现在已经是 "The Economist.recipe"，ebook-convert 会优先查找当前目录
    recipe_to_use = recipe
    print(f"📄 Using recipe: {recipe_to_use}")

    convert_args = ["ebook-convert", recipe_to_use, raw_epub]

    if issue_date:
        opt_name = RECIPE_OPTIONS.get(mag_id, "date")
        convert_args.append(f"--recipe-specific-option={opt_name}:{issue_date}")
        print(f"Using recipe option: {opt_name}:{issue_date}")

    # 执行抓取
    convert_output, code = run_command(convert_args)

    if code != 0 or not os.path.exists(raw_epub):
        print("❌ Conversion failed.")
        sys.exit(1)

    # ==================== 提取日期 ====================
    date_str = None
    # 从输出日志提取（可根据需要补充 extract_date_from_output）
    if mag_id in MAGZINES:
        date_str = None

    if not date_str:
        dt_obj = safe_strptime(issue_date)
        if dt_obj:
            date_str = dt_obj.strftime("%Y%m%d")

    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
        print(f"Warning: Using current date as fallback: {date_str}")

    print(f"Publication Date: {date_str}")

    # ==================== 保存文件 ====================
    base_name = f"{date_str} - {config['name']}"
    target_dir = os.path.join(BOOKS_DIR, date_str)
    os.makedirs(target_dir, exist_ok=True)

    final_epub = os.path.join(target_dir, f"{base_name}.epub")
    final_pdf = os.path.join(target_dir, f"{base_name}.pdf")
    cover_jpg = os.path.join(target_dir, "cover.jpg")

    os.rename(raw_epub, final_epub)

    # 提取封面
    run_command(["ebook-meta", final_epub, f"--get-cover={cover_jpg}"])

    # 转 PDF
    print("Converting to PDF...")
    run_command(["ebook-convert", final_epub, final_pdf])

    # 设置 GitHub Actions 环境变量
    if "GITHUB_ENV" in os.environ:
        try:
            with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
                f.write(f"DATE={date_str}\n")
                f.write(f"MAG_FOLDER={config['folder']}\n")
                f.write(f"MAG_NAME={config['name']}\n")
            print("✅ Environment variables set for GitHub Actions")
        except Exception as e:
            print(f"Warning: Failed to write GITHUB_ENV: {e}")

    print(f"🎉 Success! Files saved in {target_dir}")
    sys.exit(0)


if __name__ == "__main__":
    main()
