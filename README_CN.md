<div align="center">

# 馃 Hermes Memory Installer

**涓?Hermes AI Agent 娉ㄥ叆鎸佷箙鍖栭暱鏈熻蹇?鈥?鐢?gbrain 鐭ヨ瘑鍥捐氨椹卞姩**

[![Version](https://img.shields.io/badge/version-2.2.0-blue)](https://github.com/mage0535/hermes-memory-installer/releases/tag/v2.2.0)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey)]()
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)]()

[English](README.md) | [涓枃鐗圿(README_CN.md)

闆朵緷璧栬蹇嗕綋绯荤粺锛屼负 Hermes Agent 澧炲姞鎸佷箙鍖栥€佸彲妫€绱€佺敓鍛藉懆鏈熺鐞嗙殑闀挎湡璁板繂鑳藉姏銆?0 绉掑唴瀹屾垚瀹夎銆?

</div>

---

## 鐩綍

- [涓轰粈涔堥渶瑕佽繖涓」鐩甝(#涓轰粈涔堥渶瑕佽繖涓」鐩?
- [鍔熻兘鐗规€(#鍔熻兘鐗规€?
- [蹇€熷紑濮媇(#蹇€熷紑濮?
- [鏋舵瀯璇﹁В](#鏋舵瀯璇﹁В)
  - [鏁版嵁鍐欏叆娴佺▼](#鏁版嵁鍐欏叆娴佺▼)
  - [鏁版嵁璇诲彇娴佺▼](#鏁版嵁璇诲彇娴佺▼)
  - [缁存姢绠￠亾锛圕ron锛塢(#缁存姢绠￠亾cron)
  - [缁勪欢鍏ㄦ櫙鍥綸(#缁勪欢鍏ㄦ櫙鍥?
- [鑴氭湰鍙傝€冩墜鍐宂(#鑴氭湰鍙傝€冩墜鍐?
  - [鏍稿績绠￠亾鑴氭湰](#鏍稿績绠￠亾鑴氭湰)
  - [瀹堝崼涓庨獙璇佽剼鏈琞(#瀹堝崼涓庨獙璇佽剼鏈?
  - [宸ュ叿鑴氭湰](#宸ュ叿鑴氭湰)
- [閰嶇疆鎸囧崡](#閰嶇疆鎸囧崡)
  - [璁板繂浣撶敓鍛藉懆鏈熶繚鎶ら厤缃甝(#璁板繂浣撶敓鍛藉懆鏈熶繚鎶ら厤缃?
  - [棰嗗煙閰嶉閰嶇疆](#棰嗗煙閰嶉閰嶇疆)
  - [Tiered Context 鍙傛暟璋冧紭](#tiered-context-鍙傛暟璋冧紭)
- [Cron 浠诲姟绛栫暐](#cron-浠诲姟绛栫暐)
- [澧為噺鍚屾鏋舵瀯璇﹁В](#澧為噺鍚屾鏋舵瀯璇﹁В)
- [鏁版嵁瀹夊叏涓庨殣绉乚(#鏁版嵁瀹夊叏涓庨殣绉?
- [鐗堟湰鍘嗗彶](#鐗堟湰鍘嗗彶)
- [鑷磋阿](#鑷磋阿)
- [License](#license)

---

## 涓轰粈涔堥渶瑕佽繖涓」鐩?

Hermes Agent 鍐呯疆鐨?`memory()` 宸ュ叿閫傚悎鐭湡璁板繂锛屼絾鍦ㄩ暱鏈熶娇鐢ㄤ腑鏆撮湶鍑哄嚑涓牴鏈€х煭鏉匡細

### 1. 鏃犵敓鍛藉懆鏈熺鐞?
```
璁板繂浣?  [浠婂ぉ鍒氬瓨鐨刔     [90澶╁墠鐨刔     [150澶╁墠鐨刔
妲戒綅     鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈻戔枒鈻戔枒鈻戔枒鈻戔枒鈻戔枒鈻戔枒鈻戔枒鈻戔枒鈻戔枒鈻戔枒鈻戔枒鈻戔枒鈻戔枒
         鈫?鏂版潯鐩拰鏃ф潯鐩?             鈫?姘歌繙鍗犵潃浣嶇疆
           骞崇瓑绔炰簤鏈夐檺妲戒綅            涓嶄細鑷姩閲婃斁
```
姣忔潯璁板繂涓€鏃﹀啓鍏ュ氨姘镐箙鍗犳嵁妲戒綅銆傛棫鐭ヨ瘑涓嶄細鑷姩闄嶇骇锛屾柊鐭ヨ瘑娌℃湁浼樺厛鏉冦€傜粨鏋滄槸锛欰gent 鐨勪笂涓嬫枃閲屽悓鏃跺鐫€"浠婂ぉ鑲＄エ鍒嗘瀽缁撹"鍜?涓変釜鏈堝墠鐨勮繃鏈熻鍒?锛岃€屼笖鏃犳硶鍖哄垎浼樺厛绾с€?

### 2. 鏃犲垎灞傛绱?
姣忔鏂颁細璇濅粠闆跺紑濮?鈥斺€?娌℃湁涔嬪墠瀵硅瘽鐨勪笂涓嬫枃绱Н銆傚嵆浣挎槸鏈€鐩稿叧鐨勫巻鍙蹭俊鎭紝涔熼渶瑕?Agent 浠庡綋鍓?`memory()` 鐨勫揩鐓т腑纰拌繍姘斿紡鍦版壘鍒般€傛病鏈?鏈€杩戜紭鍏?銆?鐩稿叧搴︽帓搴?鎴?澶氭暟鎹簮铻嶅悎"鏈哄埗銆?

### 3. 鏃犻鍩熼殧绂?
```
褰撳墠 flat memory:
  "Magic 浠婂ぉ蹇冩儏涓嶅ソ"      鈫?鍏崇郴璁板綍
  "娌繁300鎺ㄨ崘鐢?鍥犲瓙妯″瀷"  鈫?鑲＄エ閰嶇疆
  "鎶栭煶鐭╅樀宸叉敞鍐?4涓笭閬?  鈫?鎺ㄥ箍杩愯惀
  "auxiliary蹇呴』璺熼殢涓绘ā鍨?  鈫?绯荤粺閰嶇疆
  鈫?鍏ㄩ儴娣峰湪涓€璧凤紝娌℃湁鍒嗙被锛屾病鏈夐厤棰?
```
鑲＄エ鍒嗘瀽閰嶇疆鍜屽叧绯荤姸鎬佹贩鍦ㄥ悓涓€涓墎骞冲懡鍚嶇┖闂撮噷銆備竴涓鍩熷彲浠ユ拺鐖嗘墍鏈夋Ы浣嶏紝鍙︿竴涓鍩熷垯瀹屽叏娌＄┖闂淬€?

### 4. 鏃犲弽棣堝惊鐜?
Agent 鏃犳硶鏍囪"杩欐潯淇℃伅鏈夌敤"鎴?杩欐潯宸茬粡杩囨椂"銆傛瘡娆¤皟鐢?`memory()` 杩斿洖鐨勫唴瀹归兘鏄竴瑙嗗悓浠佺殑鈥斺€旀病鏈夊涔狅紝娌℃湁杩涘寲銆?

### 鏈」鐩В鍐崇殑闂

杩欎釜瀹夎鍖呭湪 Hermes Agent 鍘熺敓 `memory()` 宸ュ叿涔嬩笂鏋勫缓浜嗕竴濂楀畬鏁寸殑璁板繂绠￠亾锛?

- **鍒嗗眰涓婁笅鏂囨敞鍏?*锛氫粠涓変釜鐙珛鏁版嵁婧愭瀯寤轰細璇濅笂涓嬫枃锛堟渶杩戜細璇?+ FTS5 鍏ㄦ枃妫€绱?+ 鐭ヨ瘑鍥捐氨锛夛紝鐢?RRF 铻嶅悎鎺掑簭
- **鐢熷懡鍛ㄦ湡鐘舵€佹満**锛氳窡韪煡璇嗘柊椴滃害锛岃嚜鍔ㄥ綊妗ｈ繃鏃跺唴瀹癸紝淇濇姢鍏抽敭椤甸潰
- **棰嗗煙闅旂**锛? 涓嫭绔嬮鍩熼厤棰濓紝闃叉鍗曚竴璇濋鎸ゅ崰鎵€鏈夋Ы浣?
- **鍐欏叆鍓嶅畧鍗?*锛氬啓鍏ュ墠妫€娴嬬煕鐩俱€佹鏌ュ閲忥紝閬垮厤闈欓粯澶辫触
- **浼氳瘽鈫掔煡璇嗗浘璋辩閬?*锛氬皢涓€娆℃€у璇濊浆鍖栦负鎸佷箙鐨勭煡璇嗗浘璋辫妭鐐?

鍏ㄩ儴 ~1,400 琛?Python锛岄浂绗笁鏂逛緷璧栥€?

---

## 鍔熻兘鐗规€?

### 馃 涓夊眰涓婁笅鏂囨敞鍏?v3锛圧RF 铻嶅悎锛?

褰?Agent 鍚姩鏂颁細璇濇椂锛屾敞鍏ュ櫒浠庝笁涓眰鏋勫缓澶嶅悎涓婁笅鏂囷細

| 灞傜骇 | 鏁版嵁婧?| 琛板噺绛栫暐 | 鏉冮噸绛栫暐 |
|------|--------|---------|---------|
| **L1** | 鏈€杩?N 涓細璇濇憳瑕侊紙SQLite `messages_fts`锛?| 鏃犺“鍑?| 濮嬬粓鍖呭惈 |
| **L2** | FTS5 鍏ㄦ枃鎼滅储锛?0K+ 鍘嗗彶娑堟伅锛?| **30 澶╁崐琛版湡** `0.5^(days/30)` | RRF 涓?L3 铻嶅悎 |
| **L3** | gbrain 鐭ヨ瘑鍥捐氨 MCP 鏌ヨ | 鑷劧琛板噺鍙栧喅浜庡浘璋辨洿鏂?| RRF 涓?L2 铻嶅悎 |

**鍏抽敭璁捐鍐崇瓥锛歀2 鍜?L3 骞惰杩愯锛屼笉鏄厹搴曞叧绯汇€?*

```
浼犵粺鐨?cascade 鏂瑰紡:
  鍏堟煡 FTS5 鈫?缁撴灉涓嶈冻鏃跺啀鏌?gbrain
  鈫?gbrain 姘歌繙鏄浜岄€夋嫨锛屽嵆浣垮畠鏈夋洿鐩稿叧鐨勪俊鎭?

RRF 铻嶅悎鏂瑰紡 (鏈」鐩?:
  FTS5 鍜?gbrain 鍚屾椂鏌ヨ
  鈫?Reciprocal Rank Fusion (k=60) 鍚堝苟涓や釜缁撴灉闆?
  鈫?鍚屾椂鍑虹幇鍦ㄤ袱涓簮涓殑鏉＄洰鑾峰緱鏄捐憲鎺掑悕鎻愬崌
  鈫?淇℃伅閲忔渶澶х殑鍐呭鎺掑湪鏈€鍓嶉潰 鉁?
```

**RRF 鍏紡璇存槑锛?*

瀵逛簬姣忎釜鏉＄洰 e锛屽叾铻嶅悎鍒嗘暟涓猴細
```
score(e) = 危 [ 1 / (k + rank_i(e)) ]
  鍏朵腑 i = 姣忎釜鏁版嵁婧愮殑鎺掑悕
  k = 铻嶅悎甯告暟锛堥粯璁?60锛?
```

- k 鍊艰秺灏忥紝鎺掑悕瓒婇潬鍓嶇殑鏉＄洰鏉冮噸瓒婂ぇ
- k 鍊艰秺澶э紝鎺掑悕鍒嗗竷瓒婂潎鍖€
- 榛樿 k=60 鍦ㄥ疄璺垫祴璇曚腑鍙栧緱浜嗘渶濂界殑骞宠　

### 馃攧 璁板繂浣撶敓鍛藉懆鏈熺姸鎬佹満

姣忎釜 gbrain page 閬靛惊鍥涙€佺敓鍛藉懆鏈燂紝鐢?`memory_lifecycle.py` 绠＄悊锛?

```
                    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                    鈹?  state:active   鈹?
                    鈹?  (姝ｅ父鐘舵€?     鈹?
                    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                             鈹?
               90 澶╂湭鏇存柊 鈹€鈹€鈹?
                             鈻?
                    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                    鈹?  state:stale    鈹?
                    鈹?  (90澶╂湭鏇存柊)   鈹?
                    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                    鈹?                鈹?
         鎵嬪姩鏇存柊 鈹€鈹€鈹?  180澶╂湭鏇存柊 鈹€鈹€鈹?
                    鈹?                鈹?
                    鈻?                鈻?
          鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
          鈹? state:active 鈹? 鈹?state:       鈹?
          鈹? (鎭㈠姝ｅ父)   鈹? 鈹? archived    鈹?
          鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹? (浠庢悳绱㈤殣钘? 鈹?
                            鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?

  鍙€? 鏄惧紡鏍囪涓?superseded 鈫?璺宠繃鏃堕棿妫€鏌ョ洿鎺ヨ繘鍏ュ綊妗ｅ€欓€?
```

**淇濇姢鏈哄埗**锛氶€氳繃鍦?YAML 閰嶇疆鏂囦欢涓畾涔夌櫧鍚嶅崟鏉ヤ繚鎶ゅ叧閿〉闈細
- 鍖归厤 `protected_slugs` 鐨勯〉闈笉浼氳繘鍏?stale/archived 鐘舵€?
- 鍖归厤 `protected_tags` 鏍囩鐨勯〉闈篃鍙椾繚鎶?
- 閰嶇疆鏂囦欢涓嶅瓨鍦ㄦ椂榛樿**鍏抽棴**淇濇姢锛堜笉淇濇姢浠讳綍椤甸潰锛?
- 浠撳簱浠ｇ爜涓?*涓嶅寘鍚换浣?*鍐呴儴椤甸潰鍚?

### 馃毀 鍐欏叆鍓嶅畧鍗?

鍦ㄥ啓鍏ユ柊鐨?memory 鏉＄洰涔嬪墠锛屼袱閬撳畧鍗€愪竴妫€鏌ワ細

#### 绗竴閬擄細瀹归噺瀹堝崼 (`memory_guard.py`)

| 鍓╀綑瀹归噺 | 琛屼负 |
|----------|------|
| > 20% | 姝ｅ父鍐欏叆 |
| 15% ~ 20% | 鍐欏叆骞惰Е鍙?compaction 棰勮 |
| < 15% | 闃绘鍐欏叆锛岃繑鍥炴槑纭敊璇?|

#### 绗簩閬擄細鐭涚浘妫€娴?(`memory_prewrite_guard.py`)

鍩轰簬姝ｅ垯鍖归厤锛堥浂 token 娑堣€楋級鎵弿宸叉湁鏉＄洰锛屾娴嬶細

```python
# 妫€娴嬪埌鐨勭煕鐩剧被鍨?
"not working" 鈫?"works great"           # 鐘舵€佸啿绐?
"I handle it" 鈫?"someone else handles"   # 褰掑睘鍐茬獊
"tomorrow" 鈫?"already done"             # 鏃堕棿鍐茬獊
```

杩斿洖缁撴瀯鍖?JSON 渚?Agent 鑷富鍐崇瓥锛?

```json
{
  "allow_write": true,
  "contradictions": [],
  "suggestion": "add",
  "capacity_check": {"ok": true, "remaining_pct": 68}
}
```

### 馃彿锔?鍙嶉鏍囩绯荤粺

Agent 鍦ㄤ娇鐢ㄤ笂涓嬫枃瀹屾垚鍝嶅簲鍚庯紝鍙互涓洪〉闈㈡墦鏍囩锛?

| 鏍囩 | 鏁堟灉 | 搴旂敤鍦烘櫙 |
|------|------|---------|
| `fb:helpful` | RRF 鍒嗘暟 +0.1 | Agent 鍙戠幇璇ヤ俊鎭鏈鎺ㄧ悊鏈夋晥 |
| `fb:misleading` | RRF 鍒嗘暟 -0.5 | Agent 鍙戠幇璇ヤ俊鎭鑷撮敊璇粨璁?|
| `fb:outdated` | 鏍囪涓哄緟瀹℃煡 | Agent 鍙戠幇淇℃伅涓庡綋鍓嶇姸鎬佷笉绗?|

鏍囩瀛樺偍鍦?gbrain page 涓婏紝璺ㄤ細璇濇寔涔呫€傚悗缁换浣?Agent 浼氳瘽閮借兘鏌ヨ鍒板弽棣堝巻鍙层€?

### 馃攲 浜旈鍩熼殧绂?

璁板繂浣撴寜棰嗗煙鍒嗗壊锛屾瘡涓鍩熸湁鐙珛鐨勯厤棰濅笂闄愶細

| 棰嗗煙 | 閰嶉 | 鐢ㄩ€?| @domain 鍓嶇紑 |
|------|------|------|-------------|
| 馃挰 Magic | 300 | 鍏崇郴鐘舵€併€佹€ф牸鐢诲儚銆佹矡閫氱瓥鐣?| `@domain:magic` |
| 馃搱 A鑲?| 400 | 閫夎偂閰嶇疆銆佸洜瀛愭潈閲嶃€佹ā鍨嬪弬鏁?| `@domain:astock` |
| 馃摙 鎺ㄥ箍 | 300 | 娓犻亾杩愯惀銆佹敞鍐岃繘搴︺€佹暟鎹粺璁?| `@domain:promo` |
| 鈿欙笍 绯荤粺 | 300 | 閰嶇疆瑙勫垯銆佹灦鏋勫喅绛栥€佸伐绋嬪摬瀛?| `@domain:system` |
| 馃摝 閫氱敤 | 300 | 鍏朵粬鏈垎绫诲唴瀹?| `@domain:misc` |

璺敱瑙勫垯锛?
```
璁板繂鏉＄洰鍐呭 鈫?瑙ｆ瀽 @domain: 鍓嶇紑 鈫?璺敱鍒板搴旈鍩?鈫?妫€鏌ラ厤棰?鈫?鍐欏叆

娌℃湁 @domain 鍓嶇紑鐨勬潯鐩?鈫?鑷姩璺敱鍒?misc
閰嶉鐢ㄥ敖鐨勯鍩?鈫?闃绘鏂板啓鍏ワ紝鎻愮ず compaction
```

### 鉁?闆朵緷璧栭獙璇?

鎵€鏈?7 涓柊鑴氭湰浠呬娇鐢?Python 鏍囧噯搴擄細

```
memory_lifecycle.py        鈫?json, sqlite3, sys, os, time, re, argparse, datetime, pathlib
tiered_context_injector.py 鈫?json, math, sqlite3, os, sys, time, re, datetime, pathlib
memory_guard.py            鈫?os, json, re, sys, pathlib
memory_prewrite_guard.py   鈫?sys, json, re, pathlib
domain_memory.py           鈫?sys, json, re, pathlib
compact_memory.py          鈫?sys, json, re, pathlib
session_to_gbrain.py       鈫?os, json, time, hashlib, sqlite3, subprocess, sys, pathlib,
                              datetime, timezone, timedelta, collections, re
```

鏃犻渶 pip install锛屾棤闇€铏氭嫙鐜锛屽鍒跺嵆鐢ㄣ€?

---

## 蹇€熷紑濮?

### 鍓嶇疆鏉′欢

- Hermes Agent 宸插畨瑁咃紙v0.11+锛?
- Python 鈮?3.9锛孲QLite 闇€鏀寔 FTS5锛堥€氬父榛樿鏀寔锛?
- 鍙€夛細瀹夎 [gbrain](https://github.com/garrytan/gbrain) 浠ヨ幏寰楃煡璇嗗浘璋卞姛鑳?

### 瀹夎姝ラ

```bash
# 鍏嬮殕浠撳簱
git clone https://github.com/mage0535/hermes-memory-installer.git
cd hermes-memory-installer

# 鏂瑰紡 A锛氫竴閿畨瑁呰剼鏈紙鎺ㄨ崘锛?
bash install.sh

# 鏂瑰紡 B锛歅ython 瀹夎鍣?
python3 installer/install.py

# 閲嶅惎 Hermes Gateway 浣块厤缃敓鏁?
systemctl restart hermes-gateway
```

### 瀹夎楠岃瘉

```bash
# 妫€鏌ユ牳蹇冪粍浠?
echo "=== 鏍稿績鑴氭湰 ==="
ls -la ~/.hermes/scripts/tiered_context_injector.py
ls -la ~/.hermes/scripts/memory_lifecycle.py
ls -la ~/.hermes/scripts/session_to_gbrain.py

echo "=== 鏁版嵁搴?==="
ls -la ~/.hermes/pool.db

echo "=== 褰掓。鐩綍 ==="
ls -d ~/.hermes/archives/*/

echo "=== Skills ==="
ls -d ~/.hermes/skills/memory-*/
```

### 棣栨杩愯娴嬭瘯

```bash
# 娴嬭瘯涓婁笅鏂囨敞鍏?
python3 ~/.hermes/scripts/tiered_context_injector.py --recall test

# 娴嬭瘯鐢熷懡鍛ㄦ湡妫€鏌ワ紙骞茶窇锛?
python3 ~/.hermes/scripts/memory_lifecycle.py --dry-run

# 娴嬭瘯浼氳瘽鍚屾锛堝共璺戯級
python3 ~/.hermes/scripts/session_to_gbrain.py --dry-run --batch 3
```

---

## 鏋舵瀯璇﹁В

```
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?                    Hermes Agent                          鈹?
鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?
鈹? 鈹?memory()     鈹? 鈹?session      鈹? 鈹?tiered_context 鈹?鈹?
鈹? 鈹?鍐欏叆         鈹? 鈹?涓婁笅鏂?      鈹? 鈹?injector(璇诲彇) 鈹?鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
          鈹?                鈹?                 鈹?
          鈻?                鈻?                 鈻?
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?                    璁板繂浣撶閬撳眰                            鈹?
鈹?                                                           鈹?
鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?
鈹? 鈹?鍐欏叆鍓嶅畧鍗?   鈹?   鈹?浼氳瘽鈫抔brain    鈹? 鈹?鐢熷懡鍛ㄦ湡绠＄悊  鈹?鈹?
鈹? 鈹?- 瀹归噺妫€鏌?   鈹?   鈹?(澧為噺鍚屾)     鈹? 鈹?- stale妫€娴? 鈹?鈹?
鈹? 鈹?- 鐭涚浘妫€娴?   鈹?   鈹?               鈹? 鈹?- 褰掓。澶勭悊   鈹?鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?
鈹?        鈹?                  鈹?                  鈹?        鈹?
鈹?        鈻?                  鈻?                  鈻?        鈹?
鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?
鈹? 鈹?棰嗗煙闅旂      鈹?   鈹?gbrain MCP     鈹? 鈹?棰嗗煙闅旂      鈹?鈹?
鈹? 鈹?5澶ч鍩熼厤棰?  鈹?   鈹?(鐭ヨ瘑鍥捐氨)     鈹? 鈹?5澶ч鍩熼厤棰?  鈹?鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
          鈹?                  鈹?                 鈹?
          鈻?                  鈻?                 鈻?
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?                    瀛樺偍灞?                                 鈹?
鈹?                                                           鈹?
鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹?
鈹? 鈹?Hermes state.db    鈹? 鈹?gbrain brain.db            鈹?   鈹?
鈹? 鈹?messages_fts       鈹? 鈹?(鐭ヨ瘑鍥捐氨 + 宓屽叆 + 鍚戦噺)   鈹?   鈹?
鈹? 鈹?(60K 鏉℃秷鎭?        鈹? 鈹?                          鈹?   鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
```

### 鏁版嵁鍐欏叆娴佺▼

```
Agent 璋冪敤 memory() 鍐欏叆鏂板唴瀹?
    鈹?
    鈻?
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?姝ラ 1: 瀹归噺瀹堝崼 (memory_guard.py)    鈹?
鈹?                                     鈹?
鈹?妫€鏌ュ墿浣欏閲?                         鈹?
鈹?  > 20%  鈫?鍏佽鍐欏叆                  鈹?
鈹?  15-20% 鈫?鍏佽鍐欏叆 + 鍙戝嚭compaction 鈹?
鈹?           棰勮                       鈹?
鈹?  < 15%  鈫?闃绘鍐欏叆锛岃繑鍥為敊璇?       鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
               鈻?
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?姝ラ 2: 鐭涚浘妫€娴?                     鈹?
鈹?(memory_prewrite_guard.py)           鈹?
鈹?                                     鈹?
鈹?鎵弿宸叉湁鏉＄洰:                         鈹?
鈹?  - 鐘舵€佸啿绐佹娴嬶紙姝ｅ垯鍖归厤锛?          鈹?
鈹?  - 褰掑睘鍐茬獊妫€娴?                     鈹?
鈹?  - 鏃堕棿鍐茬獊妫€娴?                     鈹?
鈹?                                     鈹?
鈹?杈撳嚭缁撴瀯鍖?JSON:                      鈹?
鈹?  {allow_write, contradictions,      鈹?
鈹?   suggestion, capacity_check}       鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
               鈻?
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?姝ラ 3: 棰嗗煙璺敱 (domain_memory.py)   鈹?
鈹?                                     鈹?
鈹?瑙ｆ瀽 @domain: 鍓嶇紑:                   鈹?
鈹?  @domain:magic    鈫?璺敱鍒?Magic 棰嗗煙  鈹?
鈹?  @domain:astock  鈫?璺敱鍒?A鑲?棰嗗煙   鈹?
鈹?  @domain:promo   鈫?璺敱鍒?鎺ㄥ箍 棰嗗煙  鈹?
鈹?  @domain:system  鈫?璺敱鍒?绯荤粺 棰嗗煙  鈹?
鈹?  鏃犲墠缂€          鈫?璺敱鍒?misc      鈹?
鈹?                                     鈹?
鈹?妫€鏌ラ鍩熼厤棰?                         鈹?
鈹?  閰嶉鏈敤瀹?鈫?鍏佽鍐欏叆               鈹?
鈹?  閰嶉鐢ㄥ敖   鈫?闃绘鍐欏叆锛堟彁绀篶ompaction鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
               鈻?
    memory 鍐欏叆 Hermes state.db
               鈹?
               鈻?(寮傛锛岀敱 cron 璋冨害)
    session_to_gbrain.py
    鈫?鍒涘缓/鏇存柊 gbrain page
    鈫?娣诲姞 tags + timeline
```

### 鏁版嵁璇诲彇娴佺▼

```
Agent 浼氳瘽鍚姩
    鈹?
    鈻?
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?tiered_context_injector.py                                鈹?
鈹?                                                         鈹?
鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹?
鈹? 鈹?L1: 鏈€杩?N 涓細璇?      鈹? 鈹?L3: gbrain MCP 鏌ヨ    鈹? 鈹?
鈹? 鈹?浠?state.db sessions    鈹? 鈹?浠?gbrain brain.db     鈹? 鈹?
鈹? 鈹?琛ㄨ鍙?                  鈹? 鈹?锛堢煡璇嗗浘璋辨悳绱級        鈹? 鈹?
鈹? 鈹?杩斿洖: 鎽樿鏂囨湰鍒楄〃       鈹? 鈹?杩斿洖: 鍖归厤鐨勯〉闈?鐗囨   鈹? 鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹?
鈹?            鈹?                           鈹?              鈹?
鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈻尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?             鈹?              鈹?
鈹? 鈹?L2: FTS5 鍏ㄦ枃鎼滅储       鈹?             鈹?              鈹?
鈹? 鈹?鍦?messages_fts 涓悳绱? 鈹?             鈹?              鈹?
鈹? 鈹?鎼滅储璇? recall 鍙傛暟      鈹?             鈹?              鈹?
鈹? 鈹?琛板噺: 30澶╁崐琛版湡         鈹?             鈹?              鈹?
鈹? 鈹?score *= 0.5^(days/30) 鈹?             鈹?              鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?             鈹?              鈹?
鈹?            鈹?                           鈹?              鈹?
鈹?            鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?              鈹?
鈹?                       鈻?                                鈹?
鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹?
鈹? 鈹?RRF Fusion (k=60)                                 鈹?   鈹?
鈹? 鈹?                                                    鈹?   鈹?
鈹? 鈹?瀵?L2 鍜?L3 鐨勬瘡涓粨鏋滆绠?RRF 鍒嗘暟:                鈹?   鈹?
鈹? 鈹?  score(e) = 1/(k + rank_L2(e)) + 1/(k + rank_L3(e))鈹?  鈹?
鈹? 鈹?                                                    鈹?   鈹?
鈹? 鈹?搴旂敤鍙嶉璋冩暣:                                       鈹?   鈹?
鈹? 鈹?  fb:helpful    鈫?score += 0.1                      鈹?   鈹?
鈹? 鈹?  fb:misleading 鈫?score -= 0.5                      鈹?   鈹?
鈹? 鈹?                                                    鈹?   鈹?
鈹? 鈹?鎸夊垎鏁伴檷搴忔帓鍒?                                      鈹?   鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                      鈻?
    杈撳嚭鏂囦欢:
    TIERED_CONTEXT.md     鈥?娉ㄥ叆 Agent 绯荤粺鎻愮ず璇?
    PROACTIVE_RECALL.md   鈥?棰勭儹鍙洖绾跨储
```

### 缁存姢绠￠亾锛圕ron锛?

```
姣忔棩 02:00锛堝悎骞惰蹇嗕綋缁煎悎缁存姢锛?
    鈹?
    鈹溾攢鈹€ session_to_gbrain.py      鈫?澧為噺鍚屾浼氳瘽鍒?gbrain
    鈹溾攢鈹€ tiered_context_injector   鈫?鍒锋柊 TIERED_CONTEXT.md
    鈹溾攢鈹€ memory_lifecycle          鈫?stale/archive 鐘舵€佹鏌?
    鈹斺攢鈹€ 褰掓。瀹屾暣鎬ф牳鏌?            鈫?memory 鈫?gbrain 瀵规瘮

姣忓懆涓€锛堥檮鍔狅級:
    鈹斺攢鈹€ 鍥涙簮涓€鑷存€ф牎楠?            鈫?memory vs skill vs gbrain vs file

姣忔湀 15 鏃ワ紙闄勫姞锛?
    鈹斺攢鈹€ TTL 闄嶇骇                  鈫?鏍囪 90 澶╂湭鏇存柊鐨勬潯鐩?
```

### 缁勪欢鍏ㄦ櫙鍥?

| 缁勪欢 | 绫诲瀷 | 璇█ | 渚濊禆 | 琛屾暟 |
|------|------|------|------|------|
| `tiered_context_injector.py` | 璇诲彇绠￠亾 | Python | stdlib | 384 |
| `session_to_gbrain.py` | 鍐欏叆绠￠亾 | Python | stdlib | 476 |
| `memory_lifecycle.py` | 缁存姢 | Python | stdlib | 118 |
| `domain_memory.py` | 璺敱 | Python | stdlib | 144 |
| `memory_guard.py` | 瀹堝崼 | Python | stdlib | 76 |
| `memory_prewrite_guard.py` | 瀹堝崼 | Python | stdlib | 58 |
| `compact_memory.py` | 娓呯悊 | Python | stdlib | 128 |
| `install.sh` | 瀹夎鍣?| Bash | 鈥?| ~100 |
| `installer/install.py` | 瀹夎鍣?| Python | stdlib + yaml | 127 |

---

## 鑴氭湰鍙傝€冩墜鍐?

### 鏍稿績绠￠亾鑴氭湰

#### `tiered_context_injector.py`锛?84 琛岋級

涓夊眰涓婁笅鏂囨瀯寤哄櫒銆傛槸璁板繂浣撶閬撶殑鏍稿績璇荤銆?

**鍏抽敭鍙傛暟锛?*

| 鍙傛暟 | 榛樿鍊?| 璇存槑 |
|------|--------|------|
| `HALF_LIFE_DAYS` | 30 | FTS5 鍒嗘暟琛板噺鍗婅“鏈燂紙澶╋級 |
| `TOP_K_L1` | 5 | 鍖呭惈鐨勬渶杩戜細璇濇暟 |
| `TOP_K_L2` | 5 | FTS5 缁撴灉鏁?|
| `TOP_K_L3` | 3 | gbrain 缁撴灉鏁?|
| `RRF_K` | 60 | RRF 铻嶅悎甯告暟锛堣秺灏忔帓鍚嶄紭鍔胯秺澶э級 |
| `FEEDBACK_BOOST` | 0.1 | helpful 鏍囩鍔犲垎 |
| `FEEDBACK_PENALTY` | -0.5 | misleading 鏍囩鍑忓垎 |
| `OUTPUT_CONTEXT` | `TIERED_CONTEXT.md` | 杈撳嚭鏂囦欢璺緞 |
| `OUTPUT_RECALL` | `PROACTIVE_RECALL.md` | 棰勭儹鍙洖杈撳嚭鏂囦欢 |

**L3 鏁版嵁婧愶細**
- `semantics.db` 鈫?`content_chunks` 琛紙7,600+ 鏉＄洰锛?
- `archives_fts` 鈫?FTS5 褰掓。绱㈠紩锛?,000+ 鏉＄洰锛?

**鐢ㄦ硶锛?*
```bash
# 鐢ㄦ寚瀹氫富棰樻瀯寤轰笂涓嬫枃
python3 tiered_context_injector.py --recall magic memory stock

# Cron 妯″紡锛堥潤榛橈級
python3 tiered_context_injector.py --cron
```

#### `session_to_gbrain.py`锛?76 琛岋級

灏嗙煭鏈熶細璇濇憳瑕佽浆鍖栦负鎸佷箙鐨勭煡璇嗗浘璋辫妭鐐广€?

**澧為噺鍚屾鏈哄埗锛?*

```
棣栨杩愯:
  鎵弿鍏ㄩ儴浼氳瘽 鈫?鍒涘缓 gbrain pages 鈫?
  鍐欏叆 checkpoint(gbrain_session_cursor) 鈫?瀹屾垚

鍚庣画杩愯:
  璇诲彇 checkpoint 鈫?鍙鐞嗘洿鏂扮殑浼氳瘽 鈫?
  鏇存柊 checkpoint 鈫?瀹屾垚

宕╂簝鎭㈠:
  杩愯涓柇 鈫?鏈€鍚庡凡鐭?checkpoint 鈫?
  浠庝腑鏂缁х画 鈫?骞傜瓑锛堝唴瀹瑰搱甯屽幓閲嶏級
```

**鐢ㄦ硶锛?*
```bash
# 棰勮妯″紡
python3 session_to_gbrain.py --dry-run

# 鎵瑰鐞嗭紙姣忔鏈€澶?10 鏉★級
python3 session_to_gbrain.py --batch 10

# 瀹屾暣鍥炲～
python3 session_to_gbrain.py
```

**杈撳嚭 gbrain page 缁撴瀯锛?*
```yaml
slug: session/2026-05-13-analysis
type: session
tags: [stock-analysis, a-share, 2026-05]
timeline:
  - date: 2026-05-13
    summary: "Daily stock analysis run"
    detail: "Agent scanned HS300+ZZ500, scored 100 stocks, recommended top 5"
content: |
  ## Session Summary
  - Date: 2026-05-13 09:00 CST
  - Topic: A-share daily analysis
  - Key outcome: 5 stocks recommended with entry/stop-loss targets
```

### 瀹堝崼涓庨獙璇佽剼鏈?

#### `memory_guard.py`锛?6 琛岋級

鍐欏叆鍓嶅閲忔壂鎻忥紝闃叉瀹归噺婊℃椂闈欓粯澶辫触銆?

**浣跨敤绀轰緥锛?*
```python
# 鍦?agent workflow 涓皟鐢?
from memory_guard import check_capacity

result = check_capacity()
# 杩斿洖:
# {
#   "remaining": 420,
#   "total": 2200,
#   "needs_compaction": True,
#   "action": "warn"
# }

if result["needs_compaction"]:
    print("[MEMORY GUARD] 瀹归噺涓嶈冻锛屽缓璁厛 compaction")
```

**CLI 鐢ㄦ硶锛?*
```bash
# 鍙鏌ワ紝涓嶆搷浣?
python3 memory_guard.py --check-only

# 妫€鏌ュ苟鑷姩瑙﹀彂 compaction
python3 memory_guard.py --auto-compact
```

#### `memory_prewrite_guard.py`锛?8 琛岋級

鐭涚浘妫€娴嬪櫒銆傚湪鍐欏叆鍓嶆壂鎻忓凡鏈夋潯鐩紝妫€娴嬩笌寰呭啓鍏ュ唴瀹圭殑鍐茬獊銆?

**妫€娴嬫ā寮忥細**
```python
# 鐘舵€佸弽杞ā寮?
"杩樻病鎼炲畾"  鈫?"宸茬粡瀹屾垚浜?    # 鐘舵€佸弽杞?
"涓嶅伐浣?    鈫?"杩愯姝ｅ父"     # 鐘舵€佸弽杞?

# 褰掑睘鍙樻洿
"鎴戞潵璐熻矗"  鈫?"杞氦缁欏埆浜轰簡"  # 褰掑睘鍙樻洿
"杩欐槸鏈€楂樹紭鍏堢骇" 鈫?"鏆傜紦澶勭悊" # 浼樺厛绾у彉鏇?

# 鏃堕棿鐭涚浘
"鏄庡ぉ鎴"  鈫?"宸茬粡杩囨湡"     # 鏃堕棿鐭涚浘
"涓嬪懆寮€濮?  鈫?"鍋氫簡涓ゅ懆浜?   # 鏃堕棿鐭涚浘
```

**杩斿洖鏍煎紡锛?*
```json
{
  "allow_write": true,
  "contradictions": [],
  "suggestion": "add",
  "capacity_check": {"ok": true, "remaining_pct": 68}
}
```

褰撴娴嬪埌鐭涚浘鏃讹紝`suggestion` 鍙樹负 `"replace_old_with_new"` 骞剁粰鍑哄尮閰嶇殑鏃ф潯鐩?ID銆?

#### `domain_memory.py`锛?44 琛岋級

棰嗗煙闅旂涓庨厤棰濈鐞嗗櫒銆?

**鏀寔鐨勫瓙鍛戒护锛?*
```bash
# 鍒楀嚭鏌愰鍩熺殑鎵€鏈夋潯鐩?
python3 domain_memory.py --domain magic --list

# 鏌ョ湅鍏ㄩ儴棰嗗煙浣跨敤缁熻
python3 domain_memory.py --stats
# 杈撳嚭绀轰緥:
# Domain      Used    Quota   Usage%
# magic        87/300  300     29%
# astock     312/400  400     78%
# promo      201/300  300     67%
# system     154/300  300     51%
# misc        42/300  300     14%

# 妫€鏌ユ煇棰嗗煙鏄惁杩樻湁绌洪棿
python3 domain_memory.py --domain astock --check-capacity
```

#### `compact_memory.py`锛?28 琛岋級

璁板繂浣撳帇缂╁伐鍏枫€傚垎鏋愮幇鏈夋潯鐩苟璇嗗埆鍙竻鐞嗛」銆?

**杩囨湡妯″紡鍖归厤锛堝熀浜庢鍒欙紝闈?AI锛夛細**
```
妯″紡                 绀轰緥鍖归厤
鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
宸插畬鎴恷宸蹭慨澶峾宸查儴缃? "宸蹭慨澶嶇綉缁滈棶棰?
done|fixed|resolved  "fixed the bug in v2"
60+ 澶╂棤鏇存柊          "last updated March 3"
琚柊淇℃伅鏇夸唬          "see new entry: @domain:astock #42"
```

**鐢ㄦ硶锛?*
```bash
# 鐢熸垚鍘嬬缉鎶ュ憡
python3 compact_memory.py --analyze

# 搴旂敤娓呯悊锛堣皟鐢?memory(action='remove')锛?
python3 compact_memory.py --apply
```

**杈撳嚭鎶ュ憡绀轰緥锛?*
```
=== Memory Compaction Report ===
Total entries: 47 (2200 chars, 48% used)
Stale entries found: 3
  1. "宸蹭慨澶嶏細API瓒呮椂闂" (120d old)
  2. "涓存椂鏂规锛氭墜鍔ㄩ噸鍚? (85d old)
  3. "鏃х増鍥犲瓙閰嶇疆" (宸茶鏂版潯鐩浛浠?

Recommendation: remove 3 entries 鈫?free ~280 chars (12%)
```

### 宸ュ叿鑴氭湰

v2.1.1 閬楃暀鑴氭湰锛屼繚鎸佸悜鍚庡吋瀹癸細

| 鑴氭湰 | 琛屾暟 | 鐢ㄩ€?|
|------|------|------|
| `archive_sessions.py` | 231 | 鎵归噺浼氳瘽褰掓。 |
| `auto_session_summary.py` | 72 | 鑷姩鐢熸垚浼氳瘽鎽樿 |
| `gbrain_search.py` | 99 | gbrain 鐭ヨ瘑鍥捐氨鎼滅储 CLI |
| `sync_embeddings.py` | 109 | 宓屽叆鍚戦噺鍚屾 |
| `init_db.py` | 61 | 褰掓。鏁版嵁搴撳垵濮嬪寲 |
| `daily_archive.py` | 105 | 姣忔棩褰掓。杞浆 |
| `weekly_cleanup.py` | 66 | 鍛ㄥ害缁存姢浠诲姟 |
| `test_router.py` | 60 | 娴嬭瘯鐢ㄨ矾鐢?|
| `backup.py` | 95 | 閰嶇疆澶囦唤 |
| `archive_daily.sh` | 18 | shell 褰掓。鑴氭湰 |
| `gbrain_init.sh` | 247 | gbrain 鍒濆鍖栬剼鏈?|
| `gbrain_maintain.sh` | 46 | gbrain 缁存姢鑴氭湰 |
| `embedding_server.py` | 175 | 宓屽叆寮曟搸鏈嶅姟 |

---

## 閰嶇疆鎸囧崡

### 璁板繂浣撶敓鍛藉懆鏈熶繚鎶ら厤缃?

鍒涘缓 `~/.hermes/memory_lifecycle.yaml` 鏂囦欢锛堝弬鑰?`config/memory_lifecycle.example.yaml`锛夛細

```yaml
# 鍙椾繚鎶ら〉闈?slug 鍒楄〃
protected_slugs:
  - my-project-config      # 椤圭洰閰嶇疆鏂囦欢椤甸潰
  - my-hub-operations       # 杩愯惀涓績椤甸潰

# 鍙椾繚鎶ゆ爣绛惧垪琛紙鎵€鏈夊甫姝ゆ爣绛剧殑椤甸潰锛?
protected_tags:
  - archive                 # 鎵€鏈夊綊妗ｇ被椤甸潰涔熷彈淇濇姢
  - hub                     # 鎵€鏈?hub 椤甸潰鍙椾繚鎶?
  - protected               # 鎵嬪姩鏍囪涓哄彈淇濇姢鐨?
```

**瑙勫垯寮曟搸閫昏緫锛?*
```
is_protected(slug, tags):
  if slug in protected_slugs 鈫?YES 鉁?
  if any tag in protected_tags 鈫?YES 鉁?
  otherwise 鈫?NO 鉂?
```

- 閰嶇疆鏂囦欢**涓嶅瓨鍦?*鏃讹紝榛樿涓嶄繚鎶や换浣曢〉闈?
- 淇濇姢椤甸潰涓嶄細杩涘叆 stale/archived 鐘舵€?
- 淇濇姢椤甸潰鐨?RRF 鍒嗘暟涓嶅彈 feedback 鏍囩褰卞搷

### 棰嗗煙閰嶉閰嶇疆

鍦?`domain_memory.py` 涓皟鏁?`DOMAIN_QUOTAS` 瀛楀吀锛?

```python
DOMAIN_QUOTAS = {
    "magic": 300,     # Magic 鍏崇郴绠＄悊
    "astock": 400,   # A 鑲″垎鏋愶紙闇€瑕佹洿澶氱┖闂达級
    "promo": 300,    # 鎺ㄥ箍杩愯惀
    "system": 300,   # 绯荤粺閰嶇疆
    "misc": 300,     # 閫氱敤
}

# 鎬婚噺: 1,600 瀛楃锛堟瘮 flat memory 鐨?2,200 灏?27%锛?
# 浣嗛€氳繃鍒嗗眰妫€绱紝鏈夋晥淇℃伅瀵嗗害鏇撮珮
```

### Tiered Context 鍙傛暟璋冧紭

```python
# 鍦?tiered_context_injector.py 涓皟鏁?

# 鍗婅“鏈燂細鍊艰秺灏忥紝鏃т俊鎭“鍑忚秺蹇?
HALF_LIFE_DAYS = 30
#   = 7:  涓€鍛ㄥ悗鍒嗘暟鍑忓崐锛堥€傚悎楂橀浣跨敤鍦烘櫙锛?
#   = 30: 涓€鏈堝悗鍒嗘暟鍑忓崐锛堝钩琛℃帹鑽愶級
#   = 90: 涓€瀛ｅ悗鍒嗘暟鍑忓崐锛堥€傚悎浣庨鍦烘櫙锛?

# RRF 铻嶅悎甯告暟锛氬€艰秺灏忥紝鎺掑悕浼樺娍瓒婂ぇ
RRF_K = 60
#   = 30: 鍓?3 鍚嶈幏寰楁樉钁椾紭鍔?
#   = 60: 鍒嗗竷鍧囧寑锛堟帹鑽愶紝榛樿锛?
#   = 100: 杞诲井鎺掑悕浼樺娍

# 鍙嶉璋冨垎鍔涘害
FEEDBACK_BOOST    = 0.1   # 鍔犲垎锛堜繚瀹堬級
FEEDBACK_PENALTY  = -0.5  # 鍑忓垎锛堟縺杩涳級
# 璁捐鐞嗗康锛氶敊璇俊鎭殑浠ｄ环杩滈珮浜庢紡鎺変竴鏉℃湁鐢ㄤ俊鎭?
```

---

## Cron 浠诲姟绛栫暐

### 鎺ㄨ崘璁剧疆锛堝畨瑁呮椂鑷姩閰嶇疆锛?

| 鏃堕棿 (CST) | 浠诲姟 | 棰戠巼 | 璇存槑 |
|-----------|------|------|------|
| 02:00 姣忔棩 | 鍚堝苟璁板繂浣撶淮鎶?| 姣忔棩 | gbrain 鍚屾 + 鐢熷懡鍛ㄦ湡妫€鏌?+ 涓婁笅鏂囧埛鏂?|
| 02:00 鍛ㄤ竴 | + 鍥涙簮涓€鑷存€ф牎楠?| 姣忓懆 | memory 鈫?skill 鈫?gbrain 鈫?file |
| 02:00 姣忔湀15鏃?| + TTL 闄嶇骇 | 姣忔湀 | 鏍囪 90 澶╂湭鏇存柊鏉＄洰 |
| 每 6 小时（可选） | 记忆固化：扫描最近会话，提取 durable facts，去重并清理陈旧记忆 | 周期任务 |

### 鏌ョ湅褰撳墠 Cron 浠诲姟

```bash
hermes cron list
```

### 鎵嬪姩瑙﹀彂娴嬭瘯

可选开关：

```bash
# 安装时关闭“每 6 小时记忆固化”任务
export ENABLE_MEMORY_CONSOLIDATION_CRON=0
```

```bash
# 娴嬭瘯 gbrain 鍚屾
python3 ~/.hermes/scripts/session_to_gbrain.py --dry-run

# 娴嬭瘯涓婁笅鏂囨敞鍏?
python3 ~/.hermes/scripts/tiered_context_injector.py --recall test

# 娴嬭瘯鐢熷懡鍛ㄦ湡
python3 ~/.hermes/scripts/memory_lifecycle.py --dry-run

# 涓€鑷存€ф牎楠?
python3 ~/.hermes/scripts/memory_lifecycle.py --consistency
```

---

## 澧為噺鍚屾鏋舵瀯璇﹁В

`session_to_gbrain.py` 浣跨敤 checkpoint 鏂囦欢瀹炵幇楂樻晥澧為噺鎿嶄綔锛?

### 鍚屾娴佺▼

```
绗竴杞繍琛?
  1. 鎵弿 state.db 涓墍鏈変細璇?
  2. 瀵规瘡涓細璇濓紝璁＄畻鍐呭鍝堝笇浣滀负 key
  3. 鏌ヨ gbrain 鏄惁宸插瓨鍦ㄧ浉鍚?key 鐨勯〉闈?
  4. 涓嶅瓨鍦ㄧ殑 鈫?鍒涘缓 gbrain page锛坱ag + timeline + content锛?
  5. 鍐欏叆 .gbrain_session_cursor锛堟渶鍚庡鐞嗙殑鏃堕棿鎴筹級

鍚庣画杩愯:
  1. 璇诲彇 .gbrain_session_cursor
  2. 鍙煡璇㈣鏃堕棿鎴充箣鍚庣殑浼氳瘽
  3. 瀵规瘡涓柊浼氳瘽锛岄噸澶嶆楠?2-5

骞傜瓑鎬т繚璇?
  濡傛灉鏌愭潯浼氳瘽宸插悓姝ヨ繃锛堝唴瀹瑰搱甯屽尮閰嶏級锛岃烦杩?
  濡傛灉绠￠亾涓柇锛屼笅娆¤繍琛屼粠涓柇鐨?checkpoint 缁х画
```

### 鏂囦欢浣嶇疆

```
~/.hermes/scripts/
鈹溾攢鈹€ session_to_gbrain.py        # 涓诲悓姝ヨ剼鏈?
鈹溾攢鈹€ .gbrain_session_cursor      # Checkpoint 鏂囦欢锛堣嚜鍔ㄥ垱寤猴級
鈹斺攢鈹€ ...
```

### 鎬ц兘鏁版嵁

| 鍦烘櫙 | 澶勭悊閲?| 鑰楁椂 |
|------|--------|------|
| 鏃ュ父澧為噺锛?-5 鏉℃柊浼氳瘽锛?| 5 | < 3 绉?|
| 灏忔壒鍥炲～锛?0 鏉★級 | 10 | < 10 绉?|
| 鍏ㄩ儴鍥炲～锛?00+ 鏉★級 | 100 | ~ 60 绉?|

---

## 鏁版嵁瀹夊叏涓庨殣绉?

### 闃叉鍐呴儴鏁版嵁娉勬紡

v2.2.0 鐨勪竴椤归噸瑕侀噸鏋勶細灏嗘墍鏈夊彲鑳藉寘鍚唴閮ㄦ暟鎹殑閰嶇疆浠庝唬鐮佷腑鍓ョ銆?

```
v2.1.1锛堟湁椋庨櫓锛?
  memory_lifecycle.py 涓‖缂栫爜:
    PROTECTED_SLUGS = ["magic-chat-archive-...", "hub-system-...", ...]
    PROTECTED_TAGS = ["archive", "hub", "protected", "magic", ...]
  鈫?鎺ㄩ€佸埌 GitHub 鍚庯紝鎵€鏈変汉鍙锛?

v2.2.0锛堝畨鍏級锛?鉁?
  memory_lifecycle.py 杩愯鏃朵粠 YAML 鍔犺浇:
    _load_config() 鈫?~/.hermes/memory_lifecycle.yaml
  鈫?GitHub 浠撳簱涓浂鍐呴儴鏁版嵁
  鈫?config/memory_lifecycle.example.yaml 鏄€氱敤鍗犱綅鏁版嵁
```

### 闆剁涓夋柟渚濊禆

鎵€鏈夎剼鏈粎浣跨敤 Python 鏍囧噯搴擄紝娌℃湁 pip 鍖呭紩鍏ラ闄┿€備唬鐮佸鏌ヨ寖鍥村彲鎺с€?

---

## 鐗堟湰鍘嗗彶


### v2.2.1（2026-05-25）

- 新增可选 `every 6h` 记忆固化 Cron（来自 issue #3 的建议）。
- Cron 创建具备幂等性：同名任务已存在时跳过。
- 新增关闭开关：`ENABLE_MEMORY_CONSOLIDATION_CRON=0`。
- 修复 Python 安装器 skills 路径硬编码（`/tmp/memory-repo/skills` → 仓库相对路径）。
- 修复 CLI 安装路径稳定性（不再指向临时目录，改为稳定用户目录再软链）。
- 提升 shell 安装器可移植性（移除 `readlink -f` 依赖）。
- 关联：issue #3，PR #4。

### v2.2.0锛?026-05-13锛?

#### 馃殌 鏂板 7 涓?Runtime 鑴氭湰

| 鑴氭湰 | 琛屾暟 | 鏍稿績鍔熻兘 |
|------|------|---------|
| `tiered_context_injector.py` | 384 | 涓夊眰涓婁笅鏂囨敞鍏?v3锛孯RF 铻嶅悎鎺掑簭锛屽弽棣堣皟鍒?|
| `session_to_gbrain.py` | 476 | 浼氳瘽鈫抔brain 鐭ヨ瘑鍥捐氨绠￠亾锛屽閲?checkpoint |
| `memory_lifecycle.py` | 118 | 椤甸潰鐢熷懡鍛ㄦ湡鐘舵€佹満锛孻AML 閰嶇疆淇濇姢 |
| `domain_memory.py` | 144 | 5 棰嗗煙闅旂锛岀嫭绔嬮厤棰濈鐞?|
| `memory_guard.py` | 76 | 鍐欏叆鍓嶅閲忓畧鍗紝<15% 闃绘鍐欏叆 |
| `memory_prewrite_guard.py` | 58 | 鐭涚浘妫€娴?+ 缁撴瀯鍖?JSON 杈撳嚭 |
| `compact_memory.py` | 128 | 璁板繂浣撳帇缂?v2锛岃繃鏈熸ā寮忚瘑鍒?|

#### 馃敡 淇敼 4 涓枃浠?

| 鏂囦欢 | 鏀瑰姩 |
|------|------|
| `install.sh` | 鐗堟湰 2.1.1鈫?.2.0锛涗慨澶?`/tmp/memory-repo` 纭紪鐮佽矾寰勪负鐩稿璺緞 |
| `installer/install.py` | 鐗堟湰鏍囨敞 2.0鈫?.2 |
| `README.md` / `README_CN.md` | 瀹屾暣鏂囨。鏇存柊锛堟湰鏂囷級 |
| `tests/test_smoke.py` | 淇纭紪鐮佽矾寰勶紝鏂板鑴氭湰娴嬭瘯瑕嗙洊 |

#### 馃敀 鏁版嵁瀹夊叏閲嶆瀯

- `memory_lifecycle.py`锛歚PROTECTED_SLUGS/TAGS` 纭紪鐮?鈫?澶栭儴 YAML 閰嶇疆
- 鏂板 `config/memory_lifecycle.example.yaml`锛堥€氱敤鍗犱綅鏁版嵁锛?

#### 馃搳 瑙勬ā瀵规瘮

| 鎸囨爣 | v2.1.1 | v2.2.0 | 鍙樺寲 |
|------|--------|--------|------|
| 鑴氭湰鎬绘暟 | 13 | 20 | **+54%** |
| 浠ｇ爜琛屾暟 | ~4,200 | ~5,600 | **+33%** |
| 鏂板姛鑳借剼鏈?| 0 | 7 | **鏂板** |
| 纭紪鐮佸唴閮ㄦ暟鎹?| 1澶?| 0 | 鉁?淇 |
| 纭紪鐮佺粷瀵硅矾寰?| 3澶?| 0 | 鉁?淇 |
| 绗笁鏂逛緷璧?| 0 | 0 | 鉁?涓嶅彉 |

### v2.1.1锛?026-05-09锛?

- 榛樿宓屽叆妯″瀷鍒囨崲涓?`intfloat/multilingual-e5-small`
- 妯″瀷閫夋嫨鍣ㄥ鍔?AI 鍔╂墜鑷姩瀹夎鏀寔
- 璺ㄥ钩鍙拌矾寰勬敮鎸侊紙Windows/macOS/Linux锛?

### v2.1.0锛?026-05-08锛?

- 澶氳瑷€璇箟鎼滅储
- 鏂板鑴氭湰锛氬祵鍏ュ紩鎿庛€佽嚜鍔ㄦ憳瑕併€乬brain 缁存姢
- 璺ㄥ钩鍙拌矾寰勫鐞?

### v2.0.0锛?026-05-06锛?

- gbrain 鐭ヨ瘑鍥捐氨闆嗘垚锛圡emory 2.0锛?
- 鍙岃矾寰勬悳绱紙gbrain + 鏈湴 FTS5锛?
- 鑷姩鎽樿涓?curator 鑷垜杩涘寲

---

## 鑷磋阿

鏈」鐩湪寮€鍙戣繃绋嬩腑鍙傝€冦€佸€熼壌浜嗗涓紑婧愰」鐩殑璁捐妯″紡涓庢帴鍙ｅ崗璁€傝》蹇冩劅璋㈣繖浜涢」鐩 AI Agent 鐢熸€佺郴缁熺殑璐＄尞銆?

### 鐩存帴闆嗘垚鐨勯」鐩?

- **[@mattamundson](https://github.com/mattamundson)** 鈥?[ralph-orchestrator](https://github.com/mattamundson/ralph-orchestrator) 鍜?ai-agent-memory-patterns issue 璁ㄨ涓殑閰嶇疆澶栭儴鍖栨ā寮忥紙纭紪鐮佹暟鎹?鈫?澶栭儴 YAML 閰嶇疆鏂囦欢锛夛紝浠ュ強鍩轰簬蹇収鐨勫唴瀛橀殧绂绘柟妗堬紝鐩存帴褰卞搷浜?`memory_lifecycle.py` 鐨勪繚鎶ゆ暟鎹绉绘灦鏋勫拰 `domain_memory.py` 鐨勯鍩熼殧绂昏璁°€?
- **[gbrain](https://github.com/garrytan/gbrain)** 鈥?garrytan 寮€鍙戠殑鐭ヨ瘑鍥捐氨寮曟搸锛屾彁渚涗簡 `put_page` / `add_timeline_entry` / `query` 绛?MCP 鎺ュ彛銆俙session_to_gbrain.py` 鐨勪細璇濃啋鐭ヨ瘑鍥捐氨绠￠亾鍜?`tiered_context_injector.py` 鐨?L3 妫€绱㈠潎鍩轰簬杩欎簺鎺ュ彛鏋勫缓銆?
- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** 鈥?鏈」鐩殑涓婃父鍩哄骇銆俙memory()` 宸ュ叿鐨勫啓鍏?璇诲彇鍘熻銆乣state.db` 鐨勪細璇濆瓨鍌ㄦ満鍒躲€丗TS5 鍏ㄦ枃妫€绱㈣兘鍔涳紝浠ュ強 Gateway 缃戝叧鏋舵瀯锛屾槸鎵€鏈夌閬撹剼鏈殑搴曞眰渚濊禆銆?
- **[Model Context Protocol (MCP)](https://github.com/modelcontextprotocol)** 鈥?鐢ㄤ簬 gbrain 闆嗘垚鍜屽伐鍏锋敞鍐岀殑鏍囧噯鍗忚銆係equential Thinking MCP server 鐨勬灦鏋勮璁′篃鍚彂浜嗛儴鍒嗚璁″喅绛栥€?

### 璁捐妯″紡涓庢柟娉曡鍙傝€?

- **RRF锛圧eciprocal Rank Fusion锛屽€掓暟鎺掑悕铻嶅悎锛?* 鈥?`tiered_context_injector.py` 鐨勮瀺鍚堟帓鍚嶇畻娉曞熀浜庝俊鎭绱㈤鍩熸爣鍑嗗叕寮?`score = 危 1/(k + rank)`锛宬=60銆傝绠楁硶鍦?L2锛團TS5锛夊拰 L3锛坓brain锛夌粨鏋滃苟琛屾煡璇㈠悗鎵ц铻嶅悎鎺掑簭銆?
- **[mattpocock/skills](https://github.com/mattpocock/skills)**锛堚瓙53k锛夆€?鍏朵腑鐨勭粨鏋勫寲鎵硅瘎涓庡鏌ユā寮忥紝褰卞搷浜嗗弽棣堟爣绛剧郴缁燂紙`fb:helpful/misleading/outdated`锛夊拰鐢熷懡鍛ㄦ湡鐘舵€佹満鐨勮璁℃€濊矾銆?
- **[obra/superpowers](https://github.com/obra/superpowers)**锛堚瓙175.7k锛夆€?绯荤粺鎬ц皟璇曘€佸ご鑴戦鏆淬€佸畬鎴愬墠楠岃瘉绛夋柟娉曡锛岃鍙傝€冪敤浜庢湰椤圭洰鐨勬祴璇曞拰楠岃瘉娴佺▼璁捐銆?
- **[evoiz/Agentic-Design-Patterns](https://github.com/evoiz/Agentic-Design-Patterns)**锛堚瓙562锛夆€?21 绉?Agent 鏋舵瀯璁捐妯″紡閫熸煡琛ㄤ腑鐨?涓婁笅鏂囩鐞嗘ā寮?鍜?璁板繂妯″紡"绔犺妭锛屼负涓夊眰涓婁笅鏂囩绾跨殑鏋舵瀯璁捐鎻愪緵浜嗙洿鎺ュ弬鑰冦€?
- **[msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents)**锛堚瓙90k锛夆€?澶?Agent 绯荤粺妯″紡鍜?12 澶ч鍩熷垎绫绘硶锛屽奖鍝嶄簡棰嗗煙闅旂鏋舵瀯锛? 棰嗗煙閰嶉锛夊拰浼氳瘽鈫抔brain 绠￠亾鐨勮璁°€?
- **[forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)**锛堚瓙105k锛夆€?Karpathy 鍥涢」缂栫爜鍘熷垯锛堝厛鎬濊€冦€佷繚鎸佺畝鍗曘€佹嫢鎶辨儕鍠溿€佷韩鍙楃棝鑻︼級浣滀负浠ｇ爜搴撶殑宸ョ▼鎸囧鏂归拡銆?
- **[Lum1104/UA - Understand Anything](https://github.com/Lum1104/UA)**锛堚瓙10.3k锛夆€?浠ｇ爜鈫掔煡璇嗗浘璋辩殑绠￠亾杞寲鏂规硶锛屽奖鍝嶄簡浼氳瘽鈫抔brain 鐨勫閲忓悓姝ラ€昏緫璁捐銆?
- **@domain 鍓嶇紑鍗忚** 鈥?棰嗗煙闅旂鐨勫懡鍚嶇害瀹氱敱鐢ㄦ埛鍦?v1 寮€鍙戦樁娈靛畾涔夈€傝繖鏄竴涓潵鑷疄闄呴渶姹傜殑瀹炵敤鏂规锛岃В鍐充簡涓€缁?flat memory 鐨勬贩鎺掗棶棰樸€?

### 鍩虹璁炬柦涓庡伐鍏?

- **SQLite FTS5** 鈥?`messages_fts` 鍜?`archives_fts` 琛ㄤ娇鐢ㄧ殑鍏ㄦ枃妫€绱㈠紩鎿庛€傞浂渚濊禆銆佺粡杩囧箍娉涢獙璇佺殑鏈湴鏂囨湰绱㈠紩鏂规銆?
- **Python 鏍囧噯搴?* 鈥?鎵€鏈夎剼鏈粎浣跨敤鏍囧噯搴撴ā鍧楋紙json銆乻qlite3銆乸athlib銆乨atetime銆乺e銆乭ashlib 绛夛級锛屾棤浠讳綍绗笁鏂瑰寘渚濊禆銆?
- **gbrain 宓屽叆寮曟搸鏈嶅姟** 鈥?浠?systemd 鏈嶅姟杩愯鐨勬湰鍦?sentence-transformer 宓屽叆鏈嶅姟锛屼负璇箟鎼滅储鎻愪緵鍚戦噺鏀寔銆?

### 鏂颁唬鐮佸０鏄?

鏈粨搴撲腑鐨勬墍鏈?runtime 鑴氭湰锛? 涓枃浠讹紝绾?1,393 琛岋級銆侀厤缃ā鏉裤€佸畨瑁呭櫒淇鍜屾枃妗ｅ潎涓哄叏鑷富寮€鍙戯紝鍩轰簬 MIT 寮€婧愬崗璁彂甯冦€?

## License

MIT - 璇﹁ [LICENSE](LICENSE) 鏂囦欢銆?
