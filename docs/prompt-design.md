# Prompt 設計

> 把「自然語言 → 結構化劇本」這件事,設計成 LLM 能穩定遵守的規則。本文件為領域中性說明,範例均使用通用情境。

---

## 核心理念

生成品質的瓶頸,往往不是模型不夠大,而是**指令不夠明確**。與其期待模型「自己領悟」,不如把領域知識拆成一條條可檢核的規則,再用 few-shot 範例把行為固化下來。

本專案的 system prompt 圍繞五組規則。

---

## 1. 角色與輸出限制(最高優先)

明確界定:**只輸出純 JSON 物件**。

- 禁止 code fence、前言、結語、任何非 JSON 內容。
- 不得發明工具或動作編號;缺工具時以固定備註(「需人工確認」)標記。
- 固定頂層結構:`{ "MainFlow": [...], "Sub_XXX_T": [...], "Sub_XXX_F": [...] }`。

> 把輸出格式講死,是讓下游解析穩定的第一步。

---

## 2. 複合動作拆解

使用者習慣把多個動作講成一句,但 RPA 引擎需要**原子步驟**。明確規定拆解規則:

| 使用者描述 | 拆解為 |
|---|---|
| 點擊某個 `.png` 圖像目標 | `ImageCompare`(找圖) → `MouseClick`(點擊) |
| 點擊欄位並輸入 X | `MouseClick` → `KeyIn` |
| 輸入 X 並按 Enter | `KeyIn` → `MouseClick` |

這條規則避免模型輸出「點擊欄位並輸入 Admin」這種無法執行的合併步驟。

---

## 3. 先取得,後判斷

判斷類動作需要**資料來源**。規定順序:

| 任務 | 順序 |
|---|---|
| 比較文字 | `AIOCR`(讀字) → `TextCompare` |
| 判斷數值 | `AIOCR`(讀數值) → `ParameterCount` |
| 判斷座標 / 尺寸 | `ImageCompare`(取座標) → `ParameterCount` |

模型不能憑空判斷一個還沒被讀取的值。

---

## 4. 業務路由(條件分支)

最容易出錯、也最能展現規則設計價值的部分。掛分支(`TrueCall` / `FalseCall`)前,**必須同時滿足兩個條件**:

1. 使用者**明確寫出**成立 / 不成立時要做的事。
2. 該步驟是**判斷型**工具(顏色 / 文字 / 數值)。

兩者皆成立才可掛分支;任一不成立,該步驟的分支一律留空字串。

附帶規則:

- 只有單側有描述 → 只建該側,另一側留空。
- 執行型工具(點擊 / 輸入 / 找圖 / 讀取)**永遠不掛分支**;分支只掛在其後的判斷步驟上。
- 判斷前必做的步驟 → 放主流程;條件成立才做的 → 放子劇本;條件結束後共通的 → 回到主流程。
- 子劇本命名:`Sub_` + 用途(PascalCase) + `_T`/`_F`,例如 `Sub_ShipOrder_T`。

---

## 5. 備註(Remark)規則

為避免模型在備註欄自由發揮,規定**依序判定、命中即停**:

1. 缺工具 → `"需人工確認"`
2. 使用者指定失敗跳轉至 X → `"跳轉至 X"`
3. 執行型步驟 → 留空
4. 判斷型步驟:有掛分支 → 留空;否則 → `"可能會失敗跳轉或失敗重複執行"`

並明確**禁止**在備註描述業務條件(業務條件應由分支結構表達,而非塞進文字備註)。

---

## Few-shot 範例(通用情境)

以一個電商後台流程示範拆解 + 分支:

**輸入**

> 點擊 login.png 登入,在帳號欄輸入 demo_user,按 Enter。讀取訂單狀態文字,判斷是否等於「已付款」:若是,點擊「出貨」按鈕並輸入 SHIP_OK;若否,點擊「催款」按鈕並輸入 REMIND。

**輸出**

```json
{
  "MainFlow": [
    {"GUID":"","Name":"ImageCompare","ActIdx":4,"Desc":"尋找 login.png","Remark":"可能會失敗跳轉或失敗重複執行","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"MouseClick","ActIdx":1,"Desc":"點擊 login.png","Remark":"","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"MouseClick","ActIdx":1,"Desc":"點擊帳號欄位","Remark":"","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"KeyIn","ActIdx":2,"Desc":"輸入 demo_user","Remark":"","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"MouseClick","ActIdx":1,"Desc":"按下 Enter","Remark":"","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"AIOCR","ActIdx":62,"Desc":"讀取訂單狀態字串","Remark":"","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"TextCompare","ActIdx":58,"Desc":"已付款","Remark":"","TrueCall":"Sub_ShipOrder_T","FalseCall":"Sub_RemindPay_F"}
  ],
  "Sub_ShipOrder_T": [
    {"GUID":"","Name":"MouseClick","ActIdx":1,"Desc":"點擊出貨按鈕","Remark":"","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"MouseClick","ActIdx":1,"Desc":"點擊欄位","Remark":"","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"KeyIn","ActIdx":2,"Desc":"輸入 SHIP_OK","Remark":"","TrueCall":"","FalseCall":""}
  ],
  "Sub_RemindPay_F": [
    {"GUID":"","Name":"MouseClick","ActIdx":1,"Desc":"點擊催款按鈕","Remark":"","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"MouseClick","ActIdx":1,"Desc":"點擊欄位","Remark":"","TrueCall":"","FalseCall":""},
    {"GUID":"","Name":"KeyIn","ActIdx":2,"Desc":"輸入 REMIND","Remark":"","TrueCall":"","FalseCall":""}
  ]
}
```

注意此例同時示範了:複合動作拆解(找圖→點擊、點欄位→輸入)、先取得後判斷(AIOCR→TextCompare)、雙側分支、子劇本命名,以及備註規則。

---

## 輸出前最終檢查(禁止清單)

system prompt 末段附一份「禁止清單」,要求模型自我檢查常見錯誤:

- ❌ 複合動作合併成一步
- ❌ 把分支掛在資料來源(如 AIOCR)而非後續判斷步驟
- ❌ 自行填入 GUID(應一律留空,由前端填入)

---

## 迭代方法

prompt 不是一次寫好的。流程是:

1. 用 [評測管線](evaluation.md)跑一輪,看 `problem_items`。
2. 歸納失敗題的共同模式(例如「分支總是漏掉單側」)。
3. 針對該模式補一條規則或一個 few-shot 反例。
4. 重跑評測,確認該類錯誤下降、且沒有引入新退步。

**用客觀分數驅動 prompt 迭代**,而不是憑感覺改。
