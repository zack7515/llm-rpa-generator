"""
evaluate_demo.py — 結構化評測示意(獨立、領域中性)

展示「步驟序列相似度 F1」的計分概念:
將生成劇本與標準答案的步驟,依動作編號(ActIdx)序列對齊,
配對步驟依欄位加權計分,再以 precision / recall 的調和平均(F1)彙總。

此檔為作品集示意,從零撰寫,可獨立執行,不依賴任何外部套件或 production 程式碼。
執行:  python examples/evaluate_demo.py
"""
from difflib import SequenceMatcher

# 欄位加權:用對工具最重要,其次是分支跳轉,描述與備註權重較低
FIELD_WEIGHTS = {"Name": 0.5, "branch": 0.3, "Desc": 0.1, "Remark": 0.1}


def _text_ratio(a: str, b: str) -> float:
    """兩段文字的相似度 0..1(允許用詞差異)。"""
    return SequenceMatcher(None, a, b).ratio()


def step_score(a: dict, b: dict) -> float:
    """兩個步驟的相似度 0..1,依欄位加權。"""
    score = 0.0
    if a.get("Name") == b.get("Name"):
        score += FIELD_WEIGHTS["Name"]
    if (a.get("TrueCall", ""), a.get("FalseCall", "")) == \
       (b.get("TrueCall", ""), b.get("FalseCall", "")):
        score += FIELD_WEIGHTS["branch"]
    score += FIELD_WEIGHTS["Desc"] * _text_ratio(a.get("Desc", ""), b.get("Desc", ""))
    if a.get("Remark", "") == b.get("Remark", ""):
        score += FIELD_WEIGHTS["Remark"]
    return score


def matched_score(pred: list, gold: list) -> float:
    """依 ActIdx 序列對齊,回傳所有配對步驟的相似度總和。"""
    sm = SequenceMatcher(None,
                         [s.get("ActIdx") for s in pred],
                         [s.get("ActIdx") for s in gold])
    total = 0.0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":  # 動作序列相同的區段才配對逐欄計分
            for k in range(i2 - i1):
                total += step_score(pred[i1 + k], gold[j1 + k])
    return total


def f1(pred: list, gold: list) -> dict:
    """回傳 precision / recall / f1。漏步驟與多步驟都會拉低分數。"""
    matched = matched_score(pred, gold)
    precision = matched / len(pred) if pred else 0.0
    recall = matched / len(gold) if gold else 0.0
    score = 0.0 if precision + recall == 0 else \
        2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": score}


# ----------------------------------------------------------------------
# Demo:比較「生成結果」與「標準答案」
# ----------------------------------------------------------------------
GOLD = [
    {"Name": "ImageCompare",  "ActIdx": 4, "Desc": "尋找 login.png", "TrueCall": "", "FalseCall": "", "Remark": "可能會失敗跳轉或失敗重複執行"},
    {"Name": "MouseClick",    "ActIdx": 1, "Desc": "點擊 login.png", "TrueCall": "", "FalseCall": "", "Remark": ""},
    {"Name": "AIOCR",         "ActIdx": 62, "Desc": "讀取訂單狀態字串", "TrueCall": "", "FalseCall": "", "Remark": ""},
    {"Name": "TextCompare",   "ActIdx": 58, "Desc": "已付款", "TrueCall": "Sub_1_T", "FalseCall": "Sub_2_F", "Remark": ""},
]

# 一個不錯的生成:步驟齊全,描述用詞略有差異
PRED_GOOD = [
    {"Name": "ImageCompare",  "ActIdx": 4, "Desc": "尋找 login 圖示", "TrueCall": "", "FalseCall": "", "Remark": "可能會失敗跳轉或失敗重複執行"},
    {"Name": "MouseClick",    "ActIdx": 1, "Desc": "點擊 login.png", "TrueCall": "", "FalseCall": "", "Remark": ""},
    {"Name": "AIOCR",         "ActIdx": 62, "Desc": "讀取訂單狀態", "TrueCall": "", "FalseCall": "", "Remark": ""},
    {"Name": "TextCompare",   "ActIdx": 58, "Desc": "已付款", "TrueCall": "Sub_1_T", "FalseCall": "Sub_2_F", "Remark": ""},
]

# 一個有問題的生成:漏了 AIOCR(把分支誤掛、且少一步)
PRED_BAD = [
    {"Name": "ImageCompare",  "ActIdx": 4, "Desc": "尋找 login.png", "TrueCall": "", "FalseCall": "", "Remark": "可能會失敗跳轉或失敗重複執行"},
    {"Name": "MouseClick",    "ActIdx": 1, "Desc": "點擊 login.png", "TrueCall": "", "FalseCall": "", "Remark": ""},
    {"Name": "TextCompare",   "ActIdx": 58, "Desc": "已付款", "TrueCall": "Sub_1_T", "FalseCall": "", "Remark": ""},
]


def _print(label, result):
    print(f"{label:12s}  precision={result['precision']:.3f}  "
          f"recall={result['recall']:.3f}  F1={result['f1']:.3f}")


if __name__ == "__main__":
    print("步驟序列 F1 評測示意\n" + "-" * 48)
    _print("好的生成", f1(PRED_GOOD, GOLD))
    _print("有問題的", f1(PRED_BAD, GOLD))
    print("-" * 48)
    print("可見:漏步驟會同時拉低 precision 與 recall,F1 因此下降。")
