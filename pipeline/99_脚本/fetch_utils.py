# -*- coding: utf-8 -*-
"""共享抓取工具：稳妥的 HTTP 请求、正文抽取、日期解析。"""
import gzip
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _resolve_root():
    """期次目录（ROOT）解析：环境变量 → 向上找 period.json → 脚本上级目录（历史布局）。"""
    env = (os.environ.get("CEHUI_PERIOD_DIR") or "").strip()
    if env:
        return os.path.abspath(env)
    d = os.path.abspath(os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, "period.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.isfile(os.path.join(os.path.dirname(here), "period.json")):
        return os.path.dirname(here)
    return os.path.dirname(here)


ROOT = _resolve_root()
RAW = os.path.join(ROOT, "_raw")


def http_get(url, referer=None, timeout=40, retries=3, sleep=1.5):
    """GET 一个 URL，返回 (最终URL, bytes)。带重试与 gzip 解码。"""
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", UA)
            req.add_header("Accept", "text/html,application/xhtml+xml,application/json,*/*;q=0.8")
            req.add_header("Accept-Encoding", "gzip, deflate")
            if referer:
                req.add_header("Referer", referer)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
                if "gzip" in enc:
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                return resp.geturl(), raw
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(sleep * (attempt + 1))
    raise RuntimeError(f"GET failed: {url} :: {last_err}")


def get_text(url, referer=None, timeout=40):
    """抓取并尽量按 UTF-8/GBK 正确解码。"""
    final, raw = http_get(url, referer=referer, timeout=timeout)
    for enc in ("utf-8", "gb18030"):
        try:
            return final, raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return final, raw.decode("utf-8", "ignore")


# 会构成“另起一行”的块级标签：
# 公众号新版编辑器整篇用 <section> 包段落（旧版只认 </p> 会把全文压成一行），
# 因此这里把 section／article／blockquote／figure 等也当作换行边界。
BLOCK_BREAK_RE = re.compile(
    r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>|</section>|</article>|</blockquote>|"
    r"</figure>|</figcaption>|</tr>|</dd>|</dt>|</dl>|</table>|<hr\s*/?>")


def strip_html(fragment):
    """把 HTML 片段压成纯文本（保留段落换行）。"""
    if not fragment:
        return ""
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    txt = BLOCK_BREAK_RE.sub("\n", txt)
    txt = re.sub(r"(?s)<[^>]+>", "", txt)
    txt = (txt.replace("&nbsp;", " ").replace("&amp;", "&")
              .replace("&lt;", "<").replace("&gt;", ">")
              .replace("&quot;", '"').replace("&#39;", "'").replace("&ldquo;", "“")
              .replace("&rdquo;", "”").replace("&mdash;", "—").replace("&hellip;", "…"))
    txt = re.sub(r"[ \t\u3000]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip()


def norm_date(text):
    """把各种日期写法统一成 YYYY-MM-DD。"""
    if not text:
        return ""
    m = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"t(20\d{2})(\d{2})(\d{2})_", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def save_json(path, obj):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def absolute(base_url, href):
    if not href:
        return ""
    return urllib.parse.urljoin(base_url, href.strip())
