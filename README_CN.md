<div align="center">

# Memory Sidecar v3.5

**闈㈠悜 Hermes銆丆laude Code銆丆odex銆丆ursor 绛夋櫤鑳戒綋鐨勫彲鍙戝竷澶栨寕璁板繂浣撱€?*

[![Version](https://img.shields.io/badge/version-3.5-blue?style=flat-square)](https://github.com/mage0535/hermes-memory-installer/releases)
[![Stars](https://img.shields.io/github/stars/mage0535/hermes-memory-installer?style=flat-square&logo=github&label=stars)](https://github.com/mage0535/hermes-memory-installer/stargazers)
[![Python](https://img.shields.io/badge/python-3.9+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

[**English**](README.md) | [**鏋舵瀯璇存槑**](ARCHITECTURE_CN.md)

</div>

## 杩欐槸浠€涔?
Memory Sidecar 鏄竴涓窇鍦ㄦ櫤鑳戒綋鏃佽竟鐨勫鎸傝蹇嗕綋绯荤粺锛屼笉淇敼鏅鸿兘浣撴牳蹇冧唬鐮侊紝鍙洿缁曟櫤鑳戒綋鐨勬暟鎹洰褰曞伐浣溿€傚畠浼氳鍙栦細璇濄€佹矇娣€闀挎湡鐭ヨ瘑锛屽苟鍦ㄥ悗缁换鍔′腑鎶婄浉鍏宠蹇嗛噸鏂版敞鍏ヤ笂涓嬫枃銆?
`v3.5` 鏄綋鍓嶆灦鏋勭殑瀵瑰鍙戝竷鏁寸悊鐗堟湰锛岀洰鏍囧緢鏄庣‘锛?
- 鐢?`AGENT_HOME` 椹卞姩澶氭櫤鑳戒綋瀹夎
- 璁╁垎灞傚彫鍥炪€佺煡璇嗙瑪璁板彫鍥炪€佸畨瑁呭櫒銆丆LI銆佹枃妗ｅ彛寰勫畬鍏ㄤ竴鑷?- 娓呯悊鍏紑浠撳簱涓殑绉佹湁璺緞鍜岄儴缃叉畫鐣?- 璁╅」鐩彲浠ョ湡姝ｆ斁鍒?GitHub 涓婁緵鐢ㄦ埛瀹夎浣撻獙鍜屽弽棣?
## 瀹冪湡姝ｅ寮轰簡浠€涔?
杩欎釜澶栨寕璁板繂浣撲富瑕佷粠 3 涓柟闈㈠寮烘櫤鑳戒綋锛?
1. 鎶婁細璇濇矇娣€鍒版寔涔呭眰锛岃€屼笉鏄彧鍋滅暀鍦ㄥ綋鍓嶅璇濈獥鍙ｃ€?2. 閫氳繃鐑眰銆佹俯灞傘€佸喎灞傘€佺煡璇嗗眰鑱斿悎鍙洖锛岃€屼笉鏄彧渚濊禆鍗曚竴 prompt 鍐呭瓨銆?3. 璁╂暣鐞嗚繃鐨勭煡璇嗙瑪璁颁篃鑳藉弬涓庡彫鍥烇紝閬垮厤椤圭洰鏂囨。鍜岀煡璇嗗簱涓庝細璇濊蹇嗚劚鑺傘€?
## 鍏紑鍙戝竷杈圭晫

`v3.5` 鏄庣‘鍖哄垎鈥滈€氱敤 sidecar鈥濆拰鈥滃涓讳笓鐢ㄨ繍缁磋剼鏈€濓細

- 榛樿瀹夎锛氶€氱敤澶氭櫤鑳戒綋 sidecar 杩愯鏃躲€佸畨瑁呭櫒銆丆LI銆佽蹇嗘妧鑳姐€?- 浠撳簱鍐呬繚鐣欎絾榛樿涓嶅畨瑁咃細`memory_watermark.py`銆乣memory_snapshot_backup.py`銆?
杩欎袱涓剼鏈甫鏈夋洿寮虹殑 Hermes 鍜屽涓荤幆澧冨亣璁撅紝鎵€浠ュ湪鍏紑澶氭櫤鑳戒綋瀹夎璺緞涓?**榛樿涓嶄細琚畨瑁?*锛岄伩鍏嶉檷浣庡閮ㄧ敤鎴风殑瀹夎鎴愬姛鐜囥€?
## 渚濊禆瑕佹眰

- Python `3.9+`
- PostgreSQL `16`
- 鍙敤鐨?[Hindsight](https://github.com/HindsightTechnologySolutions/hindsight)
- 鍙敤鐨?[gbrain](https://github.com/hi-ogawa/gbrain)
- 涓€涓寘鍚?`state.db` 鍜屼細璇濇枃浠剁殑鏅鸿兘浣撴暟鎹洰褰?
褰撳墠閫傞厤瀹氫綅锛?
- Hermes Agent
- Claude Code
- Codex / 绫?Codex 鏈湴鏅鸿兘浣?- Cursor 绫诲叡浜暟鎹洰褰曞満鏅?
## 蹇€熷紑濮?
```bash
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer

export AGENT_HOME="$HOME/.hermes"   # 涔熷彲浠ユ槸 ~/.claude銆亊/.cursor銆亊/.agent 绛?./install.sh
```

闈炰氦浜掑畨瑁咃細

```bash
./install.sh --noninteractive --agent-home "$HOME/.my-agent"
```

## 瀹夎妯″紡

瀹夎鍣ㄦ敮鎸?3 绉嶄緷璧栧畨瑁呭崗鍔╂ā寮忥細

- `--install-mode 3`
  榛樿妯″紡銆備紭鍏堝皾璇曟渶鑷姩鍖栫殑渚濊禆寮曞瀹夎璺緞銆?- `--install-mode 2`
  鍗婅嚜鍔ㄥ崗鍔╂ā寮忋€傝緭鍑烘帹鑽愬懡浠わ紝骞舵敮鎸佺敤鎴锋寜姝ラ缁х画瀹夎銆?- `--install-mode 1`
  浠呮娴嬫ā寮忋€備笉鏀圭郴缁燂紝鍙憡璇変綘缂轰簡浠€涔堛€?
濡傛灉妯″紡 `3` 澶辫触锛岃鍒囨崲鍒帮細

```bash
./install.sh --install-mode 2
```

濡傛灉妯″紡 `2` 浠嶇劧澶辫触锛屽啀鍒囨崲鍒帮細

```bash
./install.sh --install-mode 1
```

瀹夎鍣ㄥ悓鏃舵敮鎸佷腑鑻辨枃杈撳嚭锛?
```bash
./install.sh --lang zh
./install.sh --lang en
```

濡傛灉涓嶄紶 `--lang`锛屽畨瑁呭櫒浼氭牴鎹湰鍦扮幆澧冭嚜鍔ㄥ垽鏂€?
瀹夎鍚庢墽琛岋細

```bash
python3 "$AGENT_HOME/scripts/session_to_gbrain.py" --resume
python3 "$AGENT_HOME/scripts/memory_maintenance_cycle.py"
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

## 榛樿瀹夎鐨勮剼鏈泦

鍏紑瀹夎鍣ㄤ細鎶?10 涓繍琛屽叆鍙ｈ剼鏈拰 3 涓敮鎸佹ā鍧楅儴缃插埌 `$AGENT_HOME/scripts/`銆?
杩愯鍏ュ彛鑴氭湰锛?
- `session_to_gbrain.py`
- `memory_governance_rebuild.py`
- `memory_guardian.py`
- `memory_family_registry.py`
- `tiered_context_injector.py`
- `memory_maintenance_cycle.py`
- `sidecar_acceptance_check.py`
- `archive_sessions.py`
- `auto_session_summary.py`
- `memory_observability_report.py`

鏀寔妯″潡锛?
- `state_db_schema.py`
- `knowledge_notes.py`
- `recall_samples.py`

浠撳簱鍐呭彲閫夎緟鍔╄剼鏈細

- `memory_watermark.py`
- `memory_snapshot_backup.py`

## 鐭ヨ瘑绗旇闆嗘垚

闄や簡浼氳瘽璁板繂涔嬪锛孧emory Sidecar 杩樿兘鎺ュ叆鏁寸悊鍚庣殑 markdown 鐭ヨ瘑銆?
榛樿浼氭鏌ワ細

- `$AGENT_HOME/knowledge/notes`
- 鍘嗗彶鐭ヨ瘑鐩綍锛屽 `$AGENT_HOME/knowledge/wiki/wiki`

杩欎簺鍐呭浼氳繘鍏ョ嫭绔嬬殑 `knowledge` 鍙洖灞傦紝骞朵笌浼氳瘽妫€绱€丠indsight 浜嬪疄銆乬brain 缁撴灉涓€璧峰弬涓庤瀺鍚堝彫鍥炪€?
## Knowledge-and-Memory-Management

濡傛灉浣犲笇鏈涙妸鈥滅煡璇嗛噰闆嗐€佺煡璇嗘暣鐞嗐€佺煡璇嗘帴鍏ヨ蹇嗕綋鈥濆仛瀹屾暣锛屽缓璁厤濂椾娇鐢?[Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)銆?
瀹冩墿灞曠殑鏄笂娓哥煡璇嗚兘鍔涳紝鍖呮嫭锛?
- 缁撴瀯鍖栫煡璇嗛噰闆嗘祦绋?- wiki / 绗旇绠＄悊
- 鏇村鍚屾鍜屾帴鍏ュ伐鍏?- 鏇村畬鏁寸殑鈥滅煡璇嗕粠鍝噷鏉ャ€佸浣曠淮鎶ゃ€佸浣曡璁板繂浣撲娇鐢ㄢ€濈殑宸ヤ綔娴?
涓よ€呯殑鑱岃矗杈圭晫锛?
- `hermes-memory-installer`锛氳礋璐ｈ蹇嗕綋 sidecar 杩愯鏃跺拰瀹夎閮ㄧ讲
- `Knowledge-and-Memory-Management`锛氳礋璐ｇ煡璇嗘潵婧愩€佺煡璇嗘暣鐞嗐€佺煡璇嗕緵缁?
缁勫悎浣跨敤鏃讹紝KMM 璐熻矗浜у嚭鏁寸悊鍚庣殑鐭ヨ瘑璧勪骇锛孧emory Sidecar 璐熻矗鎶婅繖浜涜祫浜у彉鎴愭櫤鑳戒綋鍙彫鍥炵殑涓婁笅鏂囥€?
## 鍚戦噺鍙洖

璇箟鍙洖涓嶆槸寮哄埗渚濊禆锛屼絾寮虹儓寤鸿寮€鍚€傚畨瑁呭櫒鍙褰曚綘閫夋嫨鐨?embedding 妯″瀷锛宔mbedding 鏈嶅姟鏈韩闇€瑕佷綘鍗曠嫭閮ㄧ讲銆?
榛樿鎺ㄨ崘锛?
- `intfloat/multilingual-e5-small`

鍗充娇涓嶅惎鐢?embeddings锛屼互涓嬭兘鍔涗粛鐒跺彲鐢細

- FTS5 浼氳瘽妫€绱?- Hindsight 浜嬪疄鍙洖
- gbrain 鍏抽敭璇嶆绱?- 鐭ヨ瘑绗旇绱㈠紩鍙洖

## Embedding 妯″瀷閫夋嫨

瀹夎鍣ㄤ細缁х画淇濈暀浜や簰寮?Embedding 妯″瀷閫夋嫨鍔熻兘銆?
- 瀹夎杩囩▼涓彲浠ヤ粠鍐呯疆鐨勫涓ā鍨嬩腑閫夋嫨銆?- 涔熷彲浠ラ€氳繃 `--embedding` 鐩存帴浼犲叆妯″瀷 ID銆?- 浜や簰妯″紡涓嬩粛鐒舵敮鎸佸～鍐欒嚜瀹氫箟妯″瀷銆?
## 鍏煎鎬у畾浣?
杩欎釜椤圭洰杩芥眰鐨勬槸鈥滃熀浜庣ǔ瀹氭暟鎹竟鐣岀殑鍏煎鈥濓紝鑰屼笉鏄€滄繁鍏ユ瘡涓€绉嶆櫤鑳戒綋鍐呴儴鍋氳€﹀悎閫傞厤鈥濄€?
瀵规帴涓€涓櫤鑳戒綋鑷冲皯闇€瑕侊細

- 涓€涓彲鍐欑殑 agent home 鐩綍
- `state.db`
- 鍙鍙栫殑浼氳瘽鏂囦欢
- 鑳藉湪鏅鸿兘浣撹繘绋嬩箣澶栬繍琛?Python 杈呭姪鑴氭湰

杩欎篃鏄畠鑳芥湇鍔″绉嶆櫤鑳戒綋鐨勫師鍥犮€?
## 楠岃瘉鏂瑰紡

浠撳簱褰撳墠閫氳繃浠ヤ笅鏈湴楠岃瘉锛?
- 鍗曞厓娴嬭瘯涓庡洖褰掓祴璇?- 瀹夎鍣ㄥ洖婊氭祴璇?- 澶氬眰鍙洖娴嬭瘯
- 鍏紑浠撳簱鍗敓妫€鏌?
閮ㄧ讲鍚庝富瑕侀獙鏀跺懡浠わ細

```bash
python3 "$AGENT_HOME/scripts/sidecar_acceptance_check.py"
```

## 鏇存柊璁板綍

### v3.5 (2026-06-19)

- 瀹屾垚 GitHub 鍏紑鍙戝竷鏁寸悊
- 缁熶竴瀹夎鍣ㄣ€丆LI銆佹灦鏋勬枃妗ｃ€佹墜鍐屼腑鐨勭増鏈彿
- 鏄庣‘鈥滈€氱敤宸插畨瑁呰繍琛屾椂鈥濆拰鈥滃彲閫?Hermes 杩愮淮鑴氭湰鈥濈殑杈圭晫
- 琛ュ厖 KMM 鐨勬寮忎粙缁嶃€佷綔鐢ㄥ畾浣嶄笌閾炬帴
- 娓呯悊鍙戝竷闈㈠苟琛ラ綈璁稿彲璇佹枃浠?
### v3.5.1 (2026-06-20)

- 瀹夎鍣ㄦ柊澧炰腑鑻辨枃鍙岃杈撳嚭
- 澧炲姞 `1 / 2 / 3` 涓夌瀹夎妯″紡涓庡け璐ラ檷绾ц鏄?- 淇濈暀 embedding 妯″瀷閫夋嫨涓庤嚜瀹氫箟妯″瀷杈撳叆
- 琛ュ厖渚濊禆瀹夎鍗忓姪鐨勯鍏堣鏄?
### v3.2 (2026-06-08)

- 澧炲姞鍙娴嬫€ф姤鍛婅兘鍔?- 杩涗竴姝ユ敹鏁涜繍琛屾椂鍜岀幆澧冨彉閲忛厤缃?- 浼樺寲 sidecar 鏂囨。鍜岀洰褰曠粨鏋?
### v3.1.0 (2026-06-02)

- 绠€鍖栦负涓夊眰璁板繂鏋舵瀯
- 绉婚櫎鏃х殑 agentmemory 妗ユ帴灞?- 鏀圭敤 `AGENT_HOME` 椹卞姩澶氭櫤鑳戒綋瀹夎

## 鐩稿叧閾炬帴

- [ARCHITECTURE_CN.md](ARCHITECTURE_CN.md)
- [MANUAL_INSTALL.md](MANUAL_INSTALL.md)
- [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)

## 鑷磋阿

鍙傝€冮」鐩細

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Hindsight](https://github.com/HindsightTechnologySolutions/hindsight)
- [gbrain](https://github.com/hi-ogawa/gbrain)
- [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management)

鎺ㄥ姩褰撳墠鍏紑鍙戝竷褰㈡€佺殑绀惧尯鍜岀敤鎴峰弽棣堜富瑕佹潵鑷細

- GitHub issues 鍜?discussions
- 涓€绾跨敓浜х幆澧冧娇鐢ㄨ€呯殑鐩存帴鍙嶉
- 鍥寸粫鍙洖璐ㄩ噺銆佸畨瑁呴棬妲涖€佸鏅鸿兘浣撳吋瀹规€х殑鎸佺画鍙嶉

## 璁稿彲璇?
MIT銆?