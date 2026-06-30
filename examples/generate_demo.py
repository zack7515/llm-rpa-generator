"""
generate_demo.py — LLM 生成管線示意(獨立、領域中性)

展示「system prompt + 自動修復 + 規則驗證」的生成管線骨架。
預設使用 mock 輸出,不需安裝任何套件、不需 GPU 即可執行;
若本機有 Ollama,將 USE_OLLAMA 設為 True 即可實際呼叫。

此檔為作品集示意,從零撰寫,與任何 production 程式碼無關。
執行:  python examples/generate_demo.py
"""
import json
import re

# 設為 True 並安裝 `pip install ollama` 後可實際呼叫本地模型
USE_OLLAMA = False
OLLAMA_MODEL = "gemma3"

REQUIRED_FIELDS = ["GUID", "Name", "ActIdx", "Desc", "Remark", "TrueCall", "FalseCall"]

SYSTEM_PROMPT = """你是 RPA 劇本產生器,將使用者的自然語言流程描述轉為純 JSON 物件。
- 只輸出 JSON,禁止 code fence、前言、結語。
- 每個步驟含 7 欄位:GUID, Name, ActIdx, Desc, Remark, TrueCall, FalseCall。GUID 一律填 ""。
- 複合動作要拆解(點擊 .png 目標 = ImageCompare 後 MouseClick;點欄位並輸入 = MouseClick 後 KeyIn)。
- 先取得後判斷(比較文字前先 AIOCR)。
- 只有判斷型步驟可掛 TrueCall / FalseCall 分支。
頂層結構:{"MainFlow":[...], "Sub_XXX_T":[...]}"""


def repair_output(raw: str) -> str:
    """容錯修復:去除 code fence、擷取最外層 JSON、移除結尾逗號。"""
    text = raw.strip()
    # 去掉 ```json ... ``` 圍欄
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # 擷取第一個 { 到最後一個 } 之間的內容
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    # 移除物件 / 陣列結尾多餘的逗號(LLM 常見瑕疵)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def validate(parsed: dict) -> list:
    """回傳違規清單(空清單表示通過)。"""
    errors = []
    if "MainFlow" not in parsed:
        errors.append("缺少 MainFlow")
        return errors
    for flow_name, steps in parsed.items():
        for i, step in enumerate(steps):
            missing = [f for f in REQUIRED_FIELDS if f not in step]
            if missing:
                errors.append(f"{flow_name}[{i}] 缺欄位 {missing}")
            if step.get("GUID", "") != "":
                errors.append(f"{flow_name}[{i}] GUID 應為空字串")
    return errors


def call_llm(user_query: str) -> str:
    """呼叫模型;USE_OLLAMA=False 時回傳 mock 輸出(故意帶 code fence 與結尾逗號)。"""
    if USE_OLLAMA:
        import ollama
        resp = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_query},
            ],
            options={"temperature": 0.3},
        )
        return resp["message"]["content"]

    # mock:模擬一段「幾乎正確但有瑕疵」的模型輸出,用來示範 repair_output
    return """```json
{
  "MainFlow": [
    {"GUID":"","Name":"ImageCompare","ActIdx":4,"Desc":"尋找 login.png","Remark":"可能會失敗跳轉或失敗重複執行","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"MouseClick","ActIdx":1,"Desc":"點擊 login.png","Remark":"","TrueCall":"","FalseCall":""},
  ]
}
```"""


def generate(user_query: str) -> dict:
    raw = call_llm(user_query)
    repaired = repair_output(raw)
    try:
        parsed = json.loads(repaired)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON 解析失敗: {e}", "raw": raw}
    errors = validate(parsed)
    return {"ok": not errors, "parsed": parsed, "errors": errors, "raw": raw}


if __name__ == "__main__":
    query = "點擊 login.png 登入"
    print(f"使用者描述: {query}\n" + "-" * 48)
    result = generate(query)
    print("原始輸出(含瑕疵):")
    print(result["raw"])
    print("-" * 48)
    if result["ok"]:
        print("修復 + 驗證通過,結構化結果:")
        print(json.dumps(result["parsed"], ensure_ascii=False, indent=2))
    else:
        print("驗證未通過:", result.get("errors") or result.get("error"))
