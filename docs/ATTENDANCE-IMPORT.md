
支援 xlsx、CSV、文字分隔檔；舊式 xls 若需要須另核定解析套件。流程為上傳→解析→欄位映射→來源時區與格式設定→預覽→驗證→確認入庫→錯誤報告。文字支援明確指定 UTF-8／UTF-8 BOM／CP950／Shift_JIS，不靜默用猜測結果入庫。
支援多次打卡，不只兩欄上下班；原始事件不可覆寫，修正有獨立紀錄。查詢公司、員工、日期範圍、部門、來源與異常。批次有 hash、狀態、成功／失敗數、逐列錯誤及可重跑識別；事件去重優先設備事件 ID，否則使用經核定自然鍵與 row hash。跨夜班的工作日期依排班歸屬，而不是直接取 UTC 日期。


建議標準匯入欄位：employee_no,event_at,event_type,device_id,source_event_id,timezone。欄位映射允許來源檔不同名稱。保留 file_hash、row_no、raw_values、normalized_values、error_codes。commit 使用已驗證 preview revision，過期預覽不可直接入庫。大型檔分批提交前明示非全檔原子性；重試以 batch/row/event 層級冪等。匯出 CSV 防止公式注入；錯誤報告亦不得包含非授權公司資料。
