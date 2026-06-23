# -*- coding: utf-8 -*-
# Copyright (c) 2026 Tachibana Securities Co., Ltd. All rights reserved.

# 2021.07.08,   yo.
# 2022.10.20 reviced,   yo.
# 2025.07.27 reviced,   yo.
# 2026.06.21 reviced,   yo.
#
# 立花証券ｅ支店ＡＰＩ利用のサンプルコード
#
# 動作確認
# Python 3.13.5 / debian13
# API v4r9
#
# ------------------------------------------------------------------
#
# APIの基本設計について
# 
# 本APIは、プログラミング初心者や非ITエンジニアの方にも
# 利用しやすいよう、URLにJSON形式のパラメーターを付加して
# 送信する独自方式を採用しています。
# 
# 一般的なWeb APIとは異なる構成ですが、
# HTTPヘッダーやPOSTデータなどの知識を最小限に
# 抑えながら利用できることを重視しています。
# 
# このため、本APIは、URLとJSON文字列を組み立てて
# 送信するだけで利用でき、特別な知識を必要とせず、
# 各種スクリプト言語からも実装しやすいことを
# 優先した設計となっています。
#  
# ------------------------------------------------------------------
#
# 利用方法: 
# 事前に「e_api_login_pubkey.py」を実行して、仮想URL等を取得しておいてください。
# 実行は「e_api_login_pubkey.py」と同じディレクトリで行ってください。
#
# 機能: 注文約定詳細取得 を行ないます。
#
# == ご注意: ========================================
#   本番環境にに接続した場合、実際に市場に注文が出ます。
#   市場で約定した場合取り消せません。
# ==================================================
#

import urllib3
import datetime
import json
import os
import urllib.parse
from zoneinfo import ZoneInfo

# =========================================================================
#     設定項目（定数定義）
# =========================================================================
# コマンド用パラメーター -------------------
# 注文約定詳細では、注文番号、営業日は省略不可。 
S_ORDER_NUMBER = '12345678'    # 注文番号　省略不可 # 注文番号は、注文約定一覧で取得できる。新規注文、応答の該当項目。
S_EIGYOU_DAY = 'yyyymmdd'      # 営業日　省略不可   yyyymmdd　マスター情報の「CLMDateZyouhou」から取得。

# --- 共通設定項目 ------------------------------------------------------------
FNAME_URL_INFO = "file_url_info.txt"                # API接続情報ファイル
FNAME_PASSWD2 = "./.auth/file_pwd2.txt"              # 第二パスワード保存ファイル
FNAME_LOGIN_RESPONSE = "./.auth/file_login_response.txt"  # ログイン応答保存先
FNAME_INFO_P_NO = "file_info_p_no.txt"              # p_no保存ファイル

# --- 通信堅牢化のための設定項目 ---
API_TIMEOUT_SECONDS = 15.0  # タイムアウト時間（秒）: 応答がない場合15秒で切り上げる
MAX_RETRY_COUNT = 3         # 最大リトライ回数: 通信エラー時に自動再試行する回数
RETRY_INTERVAL_SECONDS = 5  # リトライ間隔（秒）: 再試行する前に待機する時間
# =========================================================================

# --- 共通ユーティリティ関数 ----------------------------------------------

def func_p_sd_date():
    """
    機能: システム時刻を"p_sd_date"の書式の文字列で返す。
    返値: "p_sd_date"の書式の文字列。 API規定書式 "YYYY.MM.DD-hh:mm:ss.sss"
    引数1: なし
    備考: 
        日本標準時（Japan Standard Time、JST）を利用のこと。
    """
    dt_now = datetime.datetime.now(
        # 日本標準時（Japan Standard Time、JST）を利用
        ZoneInfo("Asia/Tokyo")
    )
    # 年.月.日-時:分:秒 の部分を作成
    str_date = dt_now.strftime("%Y.%m.%d-%H:%M:%S")
    
    # マイクロ秒（6桁ゼロ埋め）から先頭の3桁を切り出してミリ秒を作成
    str_micro = f"{dt_now.microsecond:06d}"
    str_ms = str_micro[0:3]
    
    # ドットで結合してAPI規定書式を完成
    return str_date + "." + str_ms


def func_replace_urlencode(str_input):
    """
    URLエンコードを行う。

    URLでは、スペースや「&」「+」「?」などの記号が
    特別な意味を持つため、そのまま送信できない場合がある。
    そのため、これらの文字を「%xx」形式へ変換する。

    例:
        "A B+C" → "A%20B%2BC"

    本サンプルでは Python標準ライブラリの
    urllib.parse.quote() を利用してURLエンコードを行う。

    他言語へ移植する場合も、自前で変換処理を作成するのではなく、
    各言語が提供する標準のURLエンコード関数を利用することを推奨する。

    主な対応例:
        Python      : urllib.parse.quote()
        Java        : java.net.URLEncoder.encode()
        C#          : Uri.EscapeDataString()
        JavaScript  : encodeURIComponent()
        Go          : url.QueryEscape()

    Parameters
    ----------
    str_input : str
        URLエンコード対象文字列

    Returns
    -------
    str
        URLエンコード後の文字列
    """
    return urllib.parse.quote(str_input, safe='')


def func_read_from_file(str_fname):
    """ファイルから文字情報を一括読み込み（BOMを排除）"""
    str_read = ''
    try:
        # utf-8-sig を指定してBOMを自動的に排除しファイルを開く
        with open(str_fname, 'r', encoding='utf-8-sig') as fin:
            while True:
                line = fin.readline()
                if not line:
                    break
                str_read = str_read + line
        return str_read
    except IOError as e:
        print(f"[エラー] ファイルを読み込めません: {str_fname}")
        raise e


def func_write_to_file(str_fname_output, str_data):
    """ファイルに書き込み、権限を所有者のみ(600)に制限"""
    try:
        # 出力先フォルダの存在を確認し、存在しない場合は自動作成
        str_dir = os.path.dirname(str_fname_output)
        if str_dir and not os.path.exists(str_dir):
            os.makedirs(str_dir, exist_ok=True)

        # データをファイルへ書き込み
        with open(str_fname_output, 'w', encoding='utf-8') as fout:
            fout.write(str_data)
        
        # パーミッションを600（所有者のみ読み書き可能）に制限
        os.chmod(str_fname_output, 0o600)
    except IOError as e:
        print(f"[エラー] ファイルに書き込めません: {str_fname_output}")
        raise e


def func_get_url_info(fname):
    """
    file_url_info.txt からAPI接続設定を取得

    機能: API接続情報をファイルから取得し辞書型で返す
    引数1: 接続先情報を保存したファイル名: fname_url_info

    サポートへの問い合わせは、sJsonOfmt:'5'でお願いします。
    """
    str_url_info = func_read_from_file(fname)
    # JSON形式の文字列を辞書型で取り出す
    return  json.loads(str_url_info)    


def func_get_login_response(str_fname):
    '''
    ログインレスポンスを取得
    '''
    str_login_response = func_read_from_file(str_fname)
    dic_login_response = json.loads(str_login_response)
    return dic_login_response
    

def func_get_p_no(fname):
    """ 
    機能: p_noをファイルから取得する
    引数1: p_noを保存したファイル名（fname_info_p_no = "e_api_info_p_no.txt"）
    """
    str_p_no_info = func_read_from_file(fname)
    # JSON形式の文字列を辞書型で取り出す
    json_p_no_info = json.loads(str_p_no_info)
    int_p_no = int(json_p_no_info.get('p_no'))
    return int_p_no


def func_save_p_no(str_fname_output, int_p_no):
    """p_noを保存するためのJSONファイルを生成"""
    p_no_dict = {"p_no": str(int_p_no)}
    json_data = json.dumps(p_no_dict, indent=4)
    func_write_to_file(str_fname_output, json_data)
    print(f'現在の "p_no" を保存しました。 p_no = {int_p_no} -> {str_fname_output}')


def func_make_url_request_from_dic(
                                    auth_flg,       # ログインFlag。    login:true   login以外:false
                                    url_target,     # 接続先URL
                                    work_dic_req    # API要求項目
):
    '''
    API問合せ用完全URL（クエリパラメータ付）を作成
    
    ------------------------------------------------------------------

    APIの基本設計について

    本APIは、プログラミング初心者や非ITエンジニアの方にも
    利用しやすいよう、URLにJSON形式のパラメーターを付加して
    送信する独自方式を採用しています。

    一般的なWeb APIとは異なる構成ですが、
    HTTPヘッダーやPOSTデータなどの知識を最小限に
    抑えながら利用できることを重視しています。

    このため、本APIは、URLとJSON文字列を組み立てて
    送信するだけで利用でき、特別な知識を必要とせず、
    各種スクリプト言語からも実装しやすいことを
    優先した設計となっています。
    
    ------------------------------------------------------------------
    JSONをHTTPボディではなくURLに付加して送信します。
    詳細はAPIマニュアル参照。
    備考：
        サポートへの問い合わせを考慮し、項目ごとの改行とタブを入れてあります。
    '''
    str_url = url_target
    if auth_flg:
        str_url = urllib.parse.urljoin(str_url, 'auth/')
    json_param = json.dumps(work_dic_req, indent=4, ensure_ascii=False)
    return f"{str_url}?{json_param}"


def func_api_req(str_request_method, str_url): 
    """
    APIリクエストの送信と、Shift-JIS応答のデコード（リトライ・タイムアウト対応版）
    """
    # HTTP通信ライブラリ urllib3 を利用します。
    #
    # requests ライブラリでも同様の処理は可能ですが、
    # 本サンプルでは APIサーバーへの接続処理が分かりやすいよう、
    # より基本的な urllib3 を利用しています。
    #
    # 他言語へ移植する場合も、
    # 「HTTPクライアント生成 → リクエスト送信 → レスポンス受信」
    # の流れを対応するライブラリへ置き換えてください。

    print('--- 送信電文 -------------------------------------------')
    print(str_url)

    # 接続および読み込みのタイムアウト時間を設定
    timeout_config = urllib3.Timeout(connect=API_TIMEOUT_SECONDS, read=API_TIMEOUT_SECONDS)
    http = urllib3.PoolManager()
    
    response_data = None
    status_code = None

    # 最大試行回数に達するまで通信をリトライ
    for attempt in range(1, MAX_RETRY_COUNT + 1):
        try:
            # 2回目以降の試行（再接続）の前に、指定されたインターバル時間待機
            if attempt > 1:
                print(f"[{attempt}/{MAX_RETRY_COUNT} 回目] 再接続を試みます...（{RETRY_INTERVAL_SECONDS}秒待機）")
                time.sleep(RETRY_INTERVAL_SECONDS)

            req = http.request(str_request_method, str_url, timeout=timeout_config)
            status_code = req.status
            response_data = req.data
            break  # 正常に通信できた場合はループを抜ける

        except (TimeoutError, MaxRetryError) as ce:
            print(f"\n[警告] 通信エラーが発生しました (試行: {attempt}/{MAX_RETRY_COUNT})")
            print(f"エラー詳細: {ce}")
            
            # 最大リトライ回数を超えて失敗した場合はConnectionErrorを発生
            if attempt == MAX_RETRY_COUNT:
                raise ConnectionError(
                    f"APIサーバーへの接続に規定回数失敗しました。サーバーがメンテナンス中か、停止している可能性があります。\n"
                    f"設定されたタイムアウト時間: {API_TIMEOUT_SECONDS}秒"
                )
        except Exception as ex:
            print(f"\n[警告] 予期せぬネットワーク例外が発生しました: {ex}")
            if attempt == MAX_RETRY_COUNT:
                raise ex

    print(f"HTTP Status: {status_code}")

    # 受信した電文をShift-JISからUTF-8へデコード（不正なバイトは無視）
    str_response = response_data.decode("shift-jis", errors="ignore")
    print('--- 受信電文 -------------------------------------------')
    print(str_response)
    print('--------------------------------------------------------')

    return str_response


def func_api_request_from_dic(
                                flg_login,          # ログインFlag。    login:true   login以外:false
                                destination_url,    # 接続先URL。
                                                    #   ログイン時は、FNAME_URL_INFOから取得する接続先。
                                                    #   それ以外はログインレスポンスで指定される仮想URL。
                                dic_req_item        # API要求項目
):
    '''
    APIへの問い合わせを実行する。
    '''
    # URL文字列の作成
    str_url = func_make_url_request_from_dic(
                                                flg_login,          # ログインFlag。    login:true   login以外:false
                                                destination_url,    # 接続先URL
                                                dic_req_item        # API要求項目
    )

    # APIへの問い合わせ。
    # リクエストメソッドの指定('GET'、'POST'どちらでも動作します。)
    str_api_response = func_api_req('POST', str_url)

    # apiの返り値（JSON形式の文字列）を辞書型で取り出す
    dic_api_response = json.loads(str_api_response)
    
    return dic_api_response

# --- 共通ユーティリティ関数 ----------------------------------------------




# 参考資料（必ず最新の資料を参照してください。）
#マニュアル
#「立花証券・ｅ支店・ＡＰＩ（v4r2）、REQUEST I/F、機能毎引数項目仕様」
# (api_request_if_clumn_v4r2.pdf)
# p17/46 No.14 CLMOrderListDetail を参照してください。
#
# 14 CLMOrderListDetail
#  1	sCLMID	メッセージＩＤ	char*	I/O	"CLMOrderListDetail"
#  2	sOrderNumber	    注文番号	    char[8]	    I/O	0～99999999、左詰め、マイナスの場合なし
#  3	sEigyouDay	        営業日	        char[8]	    I/O	YYYYMMDD
#  4	sResultCode	        結果コード	    char[9]	    O	０：ＯＫ、０以外：CLMMsgTable.sMsgIdで検索しテキストを表示。0～999999999、左詰め、マイナスの場合なし
#  5	sResultText	        結果テキスト	char[512]	O	ShiftJis
#  6	sWarningCode	    警告コード	    char[9]	    O	０：ＯＫ、０以外：CLMMsgTable.sMsgIdで検索しテキストを表示。0～999999999、左詰め、マイナスの場合なし
#  7	sWarningText	    警告テキスト	char[512]	O	ShiftJis
#  8	sIssueCode	        銘柄CODE	    char[12]    O	銘柄コード（6501 等）
#  9	sOrderSizyouC	    市場	        char[2]	    O	00：東証
# 10	sOrderBaibaiKubun	売買区分	    char[1]	    O	1：売、3：買、5：現渡、7：現引
# 11	sGenkinSinyouKubun	現金信用区分	char[1]	    O	0：現物、2：新規(制度信用6ヶ月)、4：返済(制度信用6ヶ月)、6：新規(一般信用6ヶ月)、8：返済(一般信用6ヶ月)
# 12	sOrderBensaiKubun	弁済区分	    char[2]	    O	00：なし、26：制度信用6ヶ月、29：制度信用無期限、36：一般信用6ヶ月、39：一般信用無期限
# 13	sOrderCondition	    執行条件	    char[1]	    O	0：指定なし、2：寄付、4：引け、6：不成
# 14	sOrderOrderPriceKubun	注文値段区分	char[1]	O	△：未使用、1：成行、2：指値、3：親注文より高い、4：親注文より低い
# 15	sOrderOrderPrice	注文単価	    char[14]	O	0.0000～999999999.9999、左詰め、マイナスの場合なし、小数点以下桁数切詰
# 16	sOrderOrderSuryou	注文株数	    char[13]	O	照会機能仕様書 ２－８．（３）、（B1）注文詳細 No.9。0～9999999999999、左詰め、マイナスの場合なし
# 17	sOrderCurrentSuryou	有効株数	    char[13]	O	0～9999999999999、左詰め、マイナスの場合なし
# 18	sOrderStatusCode	状態コード	    char[2]	    O	[逆指値]、[通常+逆指値]注文時以外の状態
#   					                                    0：受付未済
#   					                                    1：未約定
#   					                                    2：受付エラー
#   					                                    3：訂正中
#   					                                    4：訂正完了
#   					                                    5：訂正失敗
#   					                                    6：取消中
#   					                                    7：取消完了
#   					                                    8：取消失敗
#   					                                    9：一部約定
#   					                                    10：全部約定
#   					                                    11：一部失効
#   					                                    12：全部失効
#   					                                    13：発注待ち
#   					                                    14：無効
#   					                                    15：切替注文
#   					                                    16：切替完了
#   					                                    17：切替注文失敗
#   					                                    19：繰越失効
#   					                                    20：一部障害処理
#   					                                    21：障害処理
#   					
#   					                                    [逆指値]、[通常+逆指値]注文時の状態
#   					                                    15：逆指注文(切替中)
#   					                                    16：逆指注文(未約定)
#   					                                    17：逆指注文(失敗)
#   					                                    50：発注中
# 19	sOrderStatus	    状態	        char[20]	O	
# 20	sOrderOrderDateTime	注文日付	    char[14]	O	YYYYMMDDHHMMSS,00000000000000
# 21	sOrderOrderExpireDay	有効期限	char[8]	    O	YYYYMMDD,00000000
# 22	sChannel	        チャネル	    char[1]	    O	チャネル
#   					                                    0：対面
#   					                                    1：PC
#   					                                    2：コールセンター
#   					                                    3：コールセンター
#   					                                    4：コールセンター
#   					                                    5：モバイル
#   					                                    6：リッチ
#   					                                    7：スマホ・タブレット
#   					                                    8：iPadアプリ
#   					                                    9：HOST
# 23	sGenbutuZyoutoekiKazeiC	現物口座区分	char[1]	O	譲渡益課税Ｃ（現物）。 1：特定、3：一般、5：NISA
# 24	sSinyouZyoutoekiKazeiC	建玉口座区分	char[1]	O	譲渡益課税Ｃ（信用）。1：特定、3：一般、5：NISA
# 25	sGyakusasiOrderType	逆指値注文種別	char[1]	    O	0：通常、1：逆指値、2：通常＋逆指値
# 26	sGyakusasiZyouken	逆指値条件	    char[14]	O	0.0000～999999999.9999、左詰め、マイナスの場合なし、小数点以下桁数切詰
# 27	sGyakusasiKubun	    逆指値値段区分	char[1]	    O	△：未使用、0：成行、1：指値
# 28	sGyakusasiPrice	    逆指値値段	    char[14]	O	0.0000～999999999.9999、左詰め、マイナスの場合なし、小数点以下桁数切詰
# 29	sTriggerType	    トリガータイプ	char[1]	    O	0：未トリガー、1：自動、2：手動発注、3：手動失効。初期状態は「0」で、トリガー発火後は「1/2/3」のどれかに遷移する
# 30	sTriggerTime	    トリガー日時	char[14]	O	YYYYMMDDHHMMSS,00000000000000
# 31	sUkewatasiDay	    受渡日	        char[8]	    O	YYYYMMDD,00000000
# 32	sYakuzyouPrice	    約定単価	    char[14]	O	照会機能仕様書 ２－８．（３）、（B2）約定内容詳細 No.2。0.0000～999999999.9999、左詰め、マイナスの場合なし、小数点以下桁数切詰
# 33	sYakuzyouSuryou	    約定株数	    char[13]	O	0～9999999999999、左詰め、マイナスの場合なし
# 34	sBaiBaiDaikin	    売買代金	    char[16]	O	0～9999999999999999、左詰め、マイナスの場合なし
# 35	sUtidekiKubun	    内出来区分	    char[1]	    O	△：約定分割以外、2：約定分割
# 36	sGaisanDaikin	    概算代金	    char[16]	O	0～9999999999999999、左詰め、マイナスの場合なし
# 37	sBaiBaiTesuryo	    手数料	        char[16]	O	0～9999999999999999、左詰め、マイナスの場合なし
# 38	sShouhizei	        消費税	        char[16]	O	0～9999999999999999、左詰め、マイナスの場合なし
# 39	sTatebiType	        建日種類	    char[1]	    O	△：指定なし、1：個別指定、2：建日順、3：単価益順、4：単価損順
# 40	sSizyouErrorCode	市場/取次ErrorCode	char[6]	O
#                                       照会機能仕様書 ２－８．（３）、（C1）注文履歴 No.1。
#                                       株式明細.執行市場(2桁) + 株式注文約定履歴.取引所エラー／理由コード(4桁)。
#                                       ※取引所エラーがない場合は、null。
# 41	sZougen	            リバース増減値	char[14]	O	項目は残すが使用しない
# 42	sOrderAcceptTime	市場注文受付時刻	char[14]	O	YYYYMMDDHHMMSS,00000000000000
#                                       照会機能仕様書 ２－８．（３）、（X） 以下は標準WebになくRich-I/Fにある項目 No.7。
#                                       株式明細.取引所受付／エラー時刻。
#                                       ※「通常＋逆指値」の場合は、最初の通常注文の市場注文受付時刻をセット
# 43	aYakuzyouSikkouList	約定失効リスト（※項目数に増減がある場合は、右記のカラム数も変更すること）	char[17]	O	以下レコードを配列で設定
# 44-1	sYakuzyouWarningCode	警告コード	    char[9]	O	０：ＯＫ、０以外：CLMMsgTable.sMsgIdで検索しテキストを表示。0～999999999、左詰め、マイナスの場合なし
# 45-2	sYakuzyouWarningText	警告テキスト	char[512]	O	ShiftJis
# 46-3	sYakuzyouSuryou	    約定数量	    char[13]	O	0～9999999999999、左詰め、マイナスの場合なし
# 47-4	sYakuzyouPrice	    約定価格	    char[14]	O	0.0000～999999999.9999、左詰め、マイナスの場合なし、小数点以下桁数切詰
# 48-5	sYakuzyouDate	    約定日時	    char[14]	O	YYYYMMDDHHMMSS,00000000000000
# 49	aKessaiOrderTategyokuList	決済注文建株指定リスト（※項目数に増減がある場合は、右記のカラム数も変更すること）	char[17]	O	以下レコードを配列で設定
# 50-1	sKessaiWarningCode	警告コード	    char[9]	    O	０：ＯＫ、０以外：CLMMsgTable.sMsgIdで検索しテキストを表示。0～999999999、左詰め、マイナスの場合なし
# 51-2	sKessaiWarningText	警告テキスト	char[512]	O	ShiftJis
# 52-3	sKessaiTatebiZyuni	順位	        char[9]	    O	0～999999999、左詰め、マイナスの場合なし
# 53-4	sKessaiTategyokuDay	建日	        char[8]	    O	YYYYMMDD,00000000
# 54-5	sKessaiTategyokuPrice	建単価	    char[14]	O	0.0000～999999999.9999、左詰め、マイナスの場合なし、小数点以下桁数切詰
# 55-6	sKessaiOrderSuryo	返済注文株数	char[13]	O	0～9999999999999、左詰め、マイナスの場合なし
# 56-7	sKessaiYakuzyouSuryo	約定株数	char[13]	O	0～9999999999999、左詰め、マイナスの場合なし
# 57-8	sKessaiYakuzyouPrice	約定単価	char[14]	O	0.0000～999999999.9999、左詰め、マイナスの場合なし、小数点以下桁数切詰
# 58-9	sKessaiTateTesuryou	建手数料	    char[16]	O	照会機能仕様書 ２－８．（３）、（D1）決済注文建株指定詳細 No.15。0～9999999999999999、左詰め、マイナスの場合なし
# 59-10	sKessaiZyunHibu	    順日歩	        char[16]	O	照会機能仕様書 ２－８．（３）、（D1）決済注文建株指定詳細 No.16。0～9999999999999999、左詰め、マイナスの場合なし
# 60-11	sKessaiGyakuhibu	逆日歩	        char[16]	O	照会機能仕様書 ２－８．（３）、（D1）決済注文建株指定詳細 No.17。0～9999999999999999、左詰め、マイナスの場合なし
# 61-12	sKessaiKakikaeryou	書換料	        char[16]	O	照会機能仕様書 ２－８．（３）、（D1）決済注文建株指定詳細 No.18。0～9999999999999999、左詰め、マイナスの場合なし
# 62-13	sKessaiKanrihi	    管理費	        char[16]	O	照会機能仕様書 ２－８．（３）、（D1）決済注文建株指定詳細 No.19。0～9999999999999999、左詰め、マイナスの場合なし
# 63-14	sKessaiKasikaburyou	貸株料	        char[16]	O	照会機能仕様書 ２－８．（３）、（D1）決済注文建株指定詳細 No.20。0～9999999999999999、左詰め、マイナスの場合なし
# 64-15	sKessaiSonota	    その他	        char[16]	O	照会機能仕様書 ２－８．（３）、（D1）決済注文建株指定詳細 No.21。0～9999999999999999、左詰め、マイナスの場合なし
# 65-16	sKessaiSoneki	    決済損益/受渡代金	char[16]	O	照会機能仕様書 ２－８．（３）、（D1）決済注文建株指定詳細 No.22。-999999999999999～9999999999999999、左詰め、マイナスの場合あり


# ======================================================================================================
#     プログラム始点 
# ======================================================================================================

if __name__ == "__main__":

    # 表示形式を接続情報ファイルから読み込む。
    dic_url_info = func_get_url_info(FNAME_URL_INFO)
    str_sJsonOfmt = dic_url_info.get("sJsonOfmt")

    # 22.第二パスワード
    # APIでは第２暗証番号を省略できない。 関連資料:「立花証券・e支店・API、インターフェース概要」の「3-2.ログイン、ログアウト」参照
    # URLに「#」「+」「/」「:」「=」などの記号を利用した場合エラーとなるため、URLエンコーディングを行う。
    # APIへの入力文字列（特にパスワードで記号を利用している場合）で注意が必要。
    #   '#' →   '%23'
    #   '+' →   '%2B'
    #   '/' →   '%2F'
    #   ':' →   '%3A'
    #   '=' →   '%3D'
    str_sSecondPassword = func_read_from_file(FNAME_PASSWD2).strip()
    str_sSecondPassword = func_replace_urlencode(str_sSecondPassword)        # urlエンコーディング
    
    # ログイン応答を保存した「file_login_response.txt」から、仮想URLと口座情報を取得
    dic_login_property = func_get_login_response(FNAME_LOGIN_RESPONSE)

    # 現在（前回利用した）のp_noをファイルから取得する
    my_p_no = func_get_p_no(FNAME_INFO_P_NO)
    my_p_no = my_p_no + 1
    # 更新した"p_no"を保存する。
    func_save_p_no(FNAME_INFO_P_NO, my_p_no)
    
    print()
    print('-- 注文約定詳細 の照会 ----------------------------')
    # API要求項目のセット
    dic_req_item = {
                        'p_no':             str(my_p_no),
                        'p_sd_date':        func_p_sd_date(),
                        'sCLMID':           'CLMOrderListDetail',   # 注文約定一覧詳細を指定。
                        'sOrderNumber':     S_ORDER_NUMBER,         # 注文番号　省略不可。注文番号は、注文約定一覧で取得できる。新規注文、応答の該当項目。
                        'sEigyouDay':       S_EIGYOU_DAY,           # 営業日　省略不可   yyyymmdd    マスター情報の「CLMDateZyouhou」から取得。
                        'sSecondPassword':  str_sSecondPassword,     # 22.第二パスワード    APIでは第２暗証番号を省略できない。 関連資料:「立花証券・e支店・API、インターフェース概要」の「3-2.ログイン、ログアウト」参照。
                        'sJsonOfmt':        str_sJsonOfmt           # 表示形式（サポートへの問い合わせでは'5'指定でお願いします。）
                    }

    # 'CLMOrderListDetail'は、仮想URL:'sUrlRequest'
    str_connection_url = dic_login_property.get('sUrlRequest')
    # API問い合わせ実行
    dic_return = func_api_request_from_dic(
                                                False,                  # ログインFlag。    login:true   login以外:false
                                                str_connection_url,     # 接続先URL。
                                                                        #    ログイン時は、FNAME_URL_INFOから取得する接続先。
                                                                        #   それ以外はログインレスポンスで指定される仮想URL。
                                                dic_req_item            # API要求項目
                                            )

    if dic_return is None:
        print('API接続自体の失敗')
        print('JSON形式の受信電文ではありません。接続先も含めて送信電文、受信電文を確認してください。')
    else:
        if dic_return.get('p_errno') != '-2' and dic_return.get('p_errno') != '2':
            print('p_errno', dic_return.get('p_errno'))
            print('p_err', dic_return.get('p_err'))
            print()    
            print("結果コード= ", dic_return.get("sResultCode"))           # 5
            print("結果テキスト= ", dic_return.get("sResultText"))  # 6
            print('銘柄CODE:\t', dic_return.get('sIssueCode'))
            print('市場:\t', dic_return.get('sOrderSizyouC'))
            print('売買区分:\t', dic_return.get('sOrderBaibaiKubun'))
            print('現金信用区分:\t', dic_return.get('sGenkinSinyouKubun'))
            print('弁済区分:\t', dic_return.get('sOrderBensaiKubun'))
            print('執行条件:\t', dic_return.get('sOrderCondition'))
            print('注文値段区分:\t', dic_return.get('sOrderOrderPriceKubun'))
            print('注文単価:\t', dic_return.get('sOrderOrderPrice'))
            print('注文株数:\t', dic_return.get('sOrderOrderSuryou'))
            print('有効株数:\t', dic_return.get('sOrderCurrentSuryou'))
            print('状態コード:\t', dic_return.get('sOrderStatusCode'))
            print('状態:\t', dic_return.get('sOrderStatus'))
            print('注文日付:\t', dic_return.get('sOrderOrderDateTime'))
            print('有効期限:\t', dic_return.get('sOrderOrderExpireDay'))
            print('チャネル:\t', dic_return.get('sChannel'))
            print('現物口座区分:\t', dic_return.get('sGenbutuZyoutoekiKazeiC'))
            print('建玉口座区分:\t', dic_return.get('sSinyouZyoutoekiKazeiC'))
            print('逆指値注文種別:\t', dic_return.get('sGyakusasiOrderType'))
            print('逆指値条件:\t', dic_return.get('sGyakusasiZyouken'))
            print('逆指値値段区分:\t', dic_return.get('sGyakusasiKubun'))
            print('逆指値値段:\t', dic_return.get('sGyakusasiPrice'))
            print('トリガータイプ:\t', dic_return.get('sTriggerType'))
            print('トリガー日時:\t', dic_return.get('sTriggerTime'))
            print('受渡日:\t', dic_return.get('sUkewatasiDay'))
            print('約定単価:\t', dic_return.get('sYakuzyouPrice'))
            print('約定株数:\t', dic_return.get('sYakuzyouSuryou'))
            print('売買代金:\t', dic_return.get('sBaiBaiDaikin'))
            print('内出来区分:\t', dic_return.get('sUtidekiKubun'))
            print('概算代金:\t', dic_return.get('sGaisanDaikin'))
            print('手数料:\t', dic_return.get('sBaiBaiTesuryo'))
            print('消費税:\t', dic_return.get('sShouhizei'))
            print('建日種類:\t', dic_return.get('sTatebiType'))
            print('市場/取次ErrorCode:\t', dic_return.get('sSizyouErrorCode'))
            print('リバース増減値:\t', dic_return.get('sZougen'))
            print('市場注文受付時刻:\t', dic_return.get('sOrderAcceptTime'))
            print()
            print()
            
            print('==========================')
            list_aYakuzyouSikkouList = dic_return.get("aYakuzyouSikkouList")
            if list_aYakuzyouSikkouList is not None:
                print('約定失効リスト = aYakuzyouSikkouList')
                print('件数:', len(list_aYakuzyouSikkouList))
                print()
                # 'aYakuzyouSikkouList'の返値の処理。
                # データ形式は、"aYakuzyouSikkouList":[{...},{...}, ... ,{...}]
                for i in range(len(list_aYakuzyouSikkouList)):
                    print('No.', i+1, '---------------')
                    print('警告コード:\t', list_aYakuzyouSikkouList[i].get('sYakuzyouWarningCode'))
                    print('警告テキスト:\t', list_aYakuzyouSikkouList[i].get('sYakuzyouWarningText'))
                    print('約定数量:\t', list_aYakuzyouSikkouList[i].get('sYakuzyouSuryou'))
                    print('約定価格:\t', list_aYakuzyouSikkouList[i].get('sYakuzyouPrice'))
                    print('約定日時:\t', list_aYakuzyouSikkouList[i].get('sYakuzyouDate'))
                print()
                print()

            print('==========================')
            list_aKessaiOrderTategyokuList = dic_return.get("aKessaiOrderTategyokuList")
            if list_aKessaiOrderTategyokuList is not None:
                print('決済注文建株指定リスト= aYakuzyouSikkouList')
                print('件数:', len(list_aKessaiOrderTategyokuList))
                print()
                # 'aKessaiOrderTategyokuList'の返値の処理。
                # データ形式は、"aYakuzyouSikkouList":[{...},{...}, ... ,{...}]
                for n in range(len(list_aKessaiOrderTategyokuList)):
                    print('No.', n+1, '---------------')
                    print('警告コード:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiWarningCode'))
                    print('警告テキスト:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiWarningText'))
                    print('順位:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiTatebiZyuni'))
                    print('建日:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiTategyokuDay'))
                    print('建単価:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiTategyokuPrice'))
                    print('返済注文株数:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiOrderSuryo'))
                    print('約定株数:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiYakuzyouSuryo'))
                    print('約定単価:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiYakuzyouPrice'))
                    print('建手数料:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiTateTesuryou'))
                    print('順日歩:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiZyunHibu'))
                    print('逆日歩:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiGyakuhibu'))
                    print('書換料:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiKakikaeryou'))
                    print('管理費:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiKanrihi'))
                    print('貸株料:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiKasikaburyou'))
                    print('その他:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiSonota'))
                    print('決済損益/受渡代金:\t', list_aKessaiOrderTategyokuList[n].get('sKessaiSoneki'))
                    print()
                    
        elif dic_return.get('p_errno') == '-2' :
            print("パラメーターの設定に誤りが有ります。")

        # 仮想URLが無効になっている場合
        # if dic_return.get('p_errno') == '2':
        else:
            print()
            print('p_errno', dic_return.get('p_errno'))
            print('p_err', dic_return.get('p_err'))
            print()    
            print("仮想URLが有効ではありません。")
            print("電話認証 + e_api_login_tel.py実行")
            print("を再度行い、新しく仮想URL（1日券）を取得してください。")
            
    print()    
    print()
    # 最終の'p_no'を保存する。
    func_save_p_no(FNAME_INFO_P_NO, my_p_no)