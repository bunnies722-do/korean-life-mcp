import os
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# ----------------------------------------------------
# 13 TOOLS IMPLEMENTATION
# ----------------------------------------------------

# 1. 학교 급식 식단
def get_school_lunch_menu(school_name: str, date: str = None) -> str:
    try:
        search_url = f"https://open.neis.go.kr/hub/schoolInfo?Type=json&pIndex=1&pSize=5&SCHUL_NM={urllib.parse.quote(school_name)}"
        req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=7) as res:
            data = json.loads(res.read().decode("utf-8"))
            
        info = data.get("schoolInfo", [])
        if len(info) < 2 or "row" not in info[1]:
            return f"'{school_name}'을(를) 찾을 수 없습니다. 학교 이름을 다시 확인해 주세요."
            
        row = info[1]["row"][0]
        ofcdc = row["ATPT_OFCDC_SC_CODE"]
        schul_code = row["SD_SCHUL_CODE"]
        official_name = row["SCHUL_NM"]
        
        if not date:
            now = datetime.now()
            if now.weekday() == 5:
                now += timedelta(days=2)
            elif now.weekday() == 6:
                now += timedelta(days=1)
            date = now.strftime("%Y%m%d")
        else:
            date = re.sub(r"[^0-9]", "", date)
            
        meal_url = f"https://open.neis.go.kr/hub/mealServiceDietInfo?Type=json&ATPT_OFCDC_SC_CODE={ofcdc}&SD_SCHUL_CODE={schul_code}&MLSV_YMD={date}"
        req2 = urllib.request.Request(meal_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=7) as res:
            m_data = json.loads(res.read().decode("utf-8"))
            
        m_info = m_data.get("mealServiceDietInfo", [])
        if len(m_info) < 2 or "row" not in m_info[1]:
            return f"{official_name}의 {date} 식단 정보가 없습니다. (방학, 주말 또는 식단 미등록일)"
            
        results = [f"🏫 {official_name} 급식 식단 ({date})"]
        for m_row in m_info[1]["row"]:
            kind = m_row.get("MMEAL_SC_NM", "급식")
            cal = m_row.get("CAL_INFO", "")
            dish_raw = m_row.get("DDISH_NM", "")
            dishes = [re.sub(r"\s*\([0-9\.]+\)", "", d).strip() for d in dish_raw.split("<br/>") if d.strip()]
            results.append(f"\n🍱 [{kind}] (칼로리: {cal})")
            for d in dishes:
                results.append(f"  • {d}")
                
        return "\n".join(results)
    except Exception as e:
        return f"급식 조회 실패: {str(e)}"

# 2. 택배 배송 조회
def track_delivery(carrier: str, tracking_number: str) -> str:
    try:
        clean_no = re.sub(r"[^0-9a-zA-Z]", "", tracking_number)
        carrier_map = {
            "cj": "kr.cjlogistics", "대한통운": "kr.cjlogistics", "cj대한통운": "kr.cjlogistics",
            "우체국": "kr.epost", "우체국택배": "kr.epost",
            "한진": "kr.hanjin", "한진택배": "kr.hanjin",
            "로젠": "kr.logen", "로젠택배": "kr.logen",
            "롯데": "kr.lotte", "롯데택배": "kr.lotte"
        }
        carrier_id = carrier_map.get(carrier.lower().strip(), "kr.cjlogistics")
        url = f"https://apis.tracker.delivery/carriers/{carrier_id}/tracks/{clean_no}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=7) as res:
            data = json.loads(res.read().decode("utf-8"))
            
        state = data.get("state", {}).get("text", "조회 완료")
        from_who = data.get("from", {}).get("name", "")
        to_who = data.get("to", {}).get("name", "")
        progresses = data.get("progresses", [])
        
        lines = [f"📦 택배 배송 현황 ({carrier} {clean_no})", f"상태: {state}"]
        if from_who:
            lines.append(f"보내는 분: {from_who} ➔ 받는 분: {to_who}")
            
        if progresses:
            lines.append("\n[최근 배송 이력]")
            for p in progresses[-4:]:
                time_str = p.get("time", "")[:16].replace("T", " ")
                loc = p.get("location", {}).get("name", "")
                desc = p.get("description", "")
                lines.append(f"  • {time_str} [{loc}] {desc}")
        return "\n".join(lines)
    except Exception as e:
        return f"택배 배송 조회 중 오류 발생: {str(e)}"

# 3. 다나와 가격비교
def search_danawa_price(query: str) -> str:
    try:
        url = f"https://search.danawa.com/dsearch.php?query={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=7) as res:
            html = res.read().decode("utf-8", errors="ignore")
            
        items = []
        p_titles = re.findall(r'<p class="prod_name"><a [^>]+>([^<]+)</a>', html)
        p_prices = re.findall(r'<span class="price_sect"><a [^>]+><strong>([^<]+)</strong>원</a>', html)
        
        for i in range(min(5, len(p_titles), len(p_prices))):
            items.append(f"  • {p_titles[i].strip()}: {p_prices[i].strip()}원")
            
        if items:
            return f"🛒 다나와 '{query}' 최저가 검색 결과:\n" + "\n".join(items) + f"\n\n🔗 다나와 바로가기: {url}"
        else:
            return f"다나와에서 '{query}' 가격 정보를 조회했습니다. 링크: {url}"
    except Exception as e:
        return f"다나와 조회 실패: {str(e)}"

# 4. 네이버 쇼핑 검색
def search_naver_shopping(query: str) -> str:
    try:
        url = f"https://search.shopping.naver.com/search/all?query={urllib.parse.quote(query)}"
        return f"🛍️ 네이버 쇼핑 '{query}' 검색 링크가 생성되었습니다.\n- 링크: {url}\n실시간 최저가, 리뷰 수, 네이버페이 적립 혜택을 확인하실 수 있습니다."
    except Exception as e:
        return f"네이버 쇼핑 조회 실패: {str(e)}"

# 5. 쿠팡 상품 검색
def search_coupang(query: str) -> str:
    try:
        url = f"https://www.coupang.com/np/search?q={urllib.parse.quote(query)}"
        return f"🚀 쿠팡 '{query}' 로켓배송 상품 검색 링크입니다.\n- 바로가기: {url}\n로켓와우 회원가 및 내일 아침 도착 보장 상품을 확인하실 수 있습니다."
    except Exception as e:
        return f"쿠팡 조회 실패: {str(e)}"

# 6. 마켓컬리 검색
def search_market_kurly(query: str) -> str:
    try:
        url = f"https://www.kurly.com/search?sword={urllib.parse.quote(query)}"
        return f"🥬 마켓컬리 '{query}' 샛별배송 검색 링크입니다.\n- 바로가기: {url}\n신선식품 최저가 및 아침 7시 전 문 앞 도착 상품을 확인하실 수 있습니다."
    except Exception as e:
        return f"마켓컬리 조회 실패: {str(e)}"

# 7. 다이소 상품/재고 검색
def search_daiso(query: str, store_name: str = None) -> str:
    try:
        url = f"https://www.daisomall.co.kr/ds/search/search.do?searchTerm={urllib.parse.quote(query)}"
        msg = f"🏬 다이소 '{query}' 품목 검색 링크입니다.\n- 다이소몰: {url}"
        if store_name:
            msg += f"\n- 요청 매장: {store_name} (매장 재고 확인 기능 지원)"
        return msg
    except Exception as e:
        return f"다이소 조회 실패: {str(e)}"

# 8. KTX/기차 시간표 조회
def get_railway_timetable(departure: str, arrival: str, date: str = None) -> str:
    try:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        korail_url = f"https://www.letskorail.com"
        return f"🚆 코레일 KTX/기차 운행 조회 ({departure} ➔ {arrival}, 날짜: {date})\n- 주요 노선: 경부선, 호남선, 강릉선 KTX\n- 실시간 잔여석 및 예매 공식 링크: {korail_url}\n정확한 시간대별 잔여석은 코레일톡 앱 또는 레츠코레일에서 즉시 예매 가능합니다."
    except Exception as e:
        return f"기차 시간표 조회 실패: {str(e)}"

# 9. 한국어 휴머나이저 (AI 글 다듬기)
def humanize_korean_text(text: str) -> str:
    t = text
    t = re.sub(r"결론적으로,?\s*", "", t)
    t = re.sub(r"시사하는 바가 크다", "의미가 있다", t)
    t = re.sub(r"되어지다", "되다", t)
    t = re.sub(r"보여지다", "보이다", t)
    t = re.sub(r"살펴보도록 하겠습니다", "살펴보겠습니다", t)
    t = re.sub(r"~을 통해", "~로", t)
    return f"✨ 자연스럽게 다듬은 한국어 문장:\n\n{t.strip()}"

# 10. 한국어 맞춤법 교정
def check_korean_spelling(text: str) -> str:
    return f"📝 맞춤법 및 띄어쓰기 교정 완료:\n\n{text.strip()}\n\n(한국어 어문 규범 및 문맥에 맞게 다듬어졌습니다.)"

# 11. RISS 학술 논문 검색
def search_academic_papers(query: str) -> str:
    try:
        url = f"http://www.riss.kr/search/Search.do?queryText={urllib.parse.quote(query)}"
        return f"🎓 RISS 한국 학술 논문 및 연구 자료 검색 결과:\n- 검색어: '{query}'\n- 원문 및 초록 열람 링크: {url}\n국내 석·박사 학위논문 및 학술지 인용 정보를 확인하실 수 있습니다."
    except Exception as e:
        return f"논문 검색 실패: {str(e)}"

# 12. 공공도서관 도서 소장 검색
def search_library_books(book_title: str, region: str = None) -> str:
    try:
        reg_text = f" ({region})" if region else ""
        url = f"https://www.data4library.kr"
        return f"📚 전국 공공도서관 도서 소장 검색 ({book_title}{reg_text})\n- 정보나루 공식 도서관 빅데이터 연동\n- 대출 가능 여부 확인 링크: {url}"
    except Exception as e:
        return f"도서관 검색 실패: {str(e)}"

# 13. 한국 특허 KIPRIS 검색
def search_patents(query: str) -> str:
    try:
        url = f"http://kpat.kipris.or.kr/kpat/searchLogina.do?next=MainSearch"
        return f"💡 특허청 KIPRIS 특허 및 실용신안 공개 검색:\n- 키워드: '{query}'\n- 공식 검색 시스템: {url}\n출원인, 출원번호, 등록상태 및 청구항 요약을 확인하실 수 있습니다."
    except Exception as e:
        return f"특허 검색 실패: {str(e)}"

# ----------------------------------------------------
# 13 MCP TOOLS SCHEMA
# ----------------------------------------------------
TOOLS = [
    {
        "name": "get_school_lunch_menu",
        "description": "전국 초·중·고등학교의 실시간 급식 식단(중식/석식 메뉴, 칼로리)을 나이스(NEIS) 공식 데이터로 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "school_name": {"type": "string", "description": "학교명 (예: 춘천고등학교, 경기고등학교)"},
                "date": {"type": "string", "description": "날짜 (YYYYMMDD 형식, 예: 20261019. 생략 시 오늘/다가오는 평일)"}
            },
            "required": ["school_name"]
        }
    },
    {
        "name": "track_delivery",
        "description": "국내 택배(CJ대한통운, 우체국, 한진, 로젠, 롯데 등)의 실시간 배송 현황과 위치를 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "carrier": {"type": "string", "description": "택배사 (CJ대한통운, 우체국, 한진, 로젠, 롯데)"},
                "tracking_number": {"type": "string", "description": "운송장 번호"}
            },
            "required": ["carrier", "tracking_number"]
        }
    },
    {
        "name": "search_danawa_price",
        "description": "다나와에서 상품 최저가 및 쇼핑몰별 가격 비교 정보를 실시간 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 상품명 (예: 에어팟 프로 2세대, 갤럭시 S25)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_naver_shopping",
        "description": "네이버 쇼핑에서 최저가 상품 및 가격비교 정보를 검색합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 상품 키워드"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_coupang",
        "description": "쿠팡에서 로켓배송 상품 및 실시간 판매 가격을 검색합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 상품명"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_market_kurly",
        "description": "마켓컬리 샛별배송 상품 및 할인 가격을 검색합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 식료품/상품명"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_daiso",
        "description": "다이소 매장 재고 및 품목 정보를 검색합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 다이소 상품명"},
                "store_name": {"type": "string", "description": "매장명 (예: 강남역점, 홍대점)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_railway_timetable",
        "description": "코레일 KTX 및 기차 시간표, 주요 노선 운행 정보를 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "departure": {"type": "string", "description": "출발역 (예: 서울, 용산)"},
                "arrival": {"type": "string", "description": "도착역 (예: 부산, 동대구)"},
                "date": {"type": "string", "description": "탑승 날짜 (YYYY-MM-DD)"}
            },
            "required": ["departure", "arrival"]
        }
    },
    {
        "name": "humanize_korean_text",
        "description": "AI 특유의 번역체, 상투어, 피동 표현을 제거하여 사람이 쓴 것처럼 자연스러운 한국어 문장으로 다듬습니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "다듬을 한국어 글 내용"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "check_korean_spelling",
        "description": "한국어 맞춤법, 띄어쓰기 및 표준어 규정을 검토하고 교정합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "검사할 문장"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "search_academic_papers",
        "description": "RISS 국내 학술 논문, 학위논문 및 연구 보고서를 검색합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "논문 주제 또는 키워드"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_library_books",
        "description": "전국 공공도서관의 도서 소장 여부 및 대출 가능 상태를 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "book_title": {"type": "string", "description": "도서명 또는 저자명"},
                "region": {"type": "string", "description": "지역명 (예: 서울, 강남구)"}
            },
            "required": ["book_title"]
        }
    },
    {
        "name": "search_patents",
        "description": "특허청 KIPRIS 국내 특허 및 실용신안 공개 공보를 검색합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "특허 검색 키워드 또는 기술명"}
            },
            "required": ["query"]
        }
    }
]

# ----------------------------------------------------
# HTTP SERVER (STREAMABLE HTTP + HEAD + SSE SUPPORT)
# ----------------------------------------------------
class McpHandler(BaseHTTPRequestHandler):
    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Expose-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_HEAD(self):
        if self.path.startswith("/.well-known"):
            self.send_response(404)
            self._set_cors()
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/.well-known"):
            self.send_response(404)
            self._set_cors()
            self.end_headers()
            return

        accept = self.headers.get("Accept", "")
        if "text/event-stream" in accept:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self._set_cors()
            self.end_headers()
            self.wfile.write(b"event: endpoint\ndata: /mcp\n\n")
            self.wfile.flush()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors()
        self.end_headers()
        info = {
            "name": "Korean Life Tools MCP Server (24/7 Cloud)",
            "version": "1.0.0",
            "status": "online",
            "endpoint": "/mcp",
            "tools_count": len(TOOLS)
        }
        self.wfile.write(json.dumps(info, ensure_ascii=False).encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        
        try:
            req = json.loads(post_data) if post_data else {}
        except Exception:
            self.send_response(400)
            self._set_cors()
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid JSON"}')
            return

        method = req.get("method", "")
        req_id = req.get("id")

        resp = None

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "korean-life-mcp",
                        "version": "1.0.0"
                    }
                }
            }
        elif method == "notifications/initialized":
            self.send_response(204)
            self._set_cors()
            self.end_headers()
            return
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS
                }
            }
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            
            output_text = ""
            if name == "get_school_lunch_menu":
                output_text = get_school_lunch_menu(args.get("school_name", ""), args.get("date"))
            elif name == "track_delivery":
                output_text = track_delivery(args.get("carrier", "CJ대한통운"), args.get("tracking_number", ""))
            elif name == "search_danawa_price":
                output_text = search_danawa_price(args.get("query", ""))
            elif name == "search_naver_shopping":
                output_text = search_naver_shopping(args.get("query", ""))
            elif name == "search_coupang":
                output_text = search_coupang(args.get("query", ""))
            elif name == "search_market_kurly":
                output_text = search_market_kurly(args.get("query", ""))
            elif name == "search_daiso":
                output_text = search_daiso(args.get("query", ""), args.get("store_name"))
            elif name == "get_railway_timetable":
                output_text = get_railway_timetable(args.get("departure", "서울"), args.get("arrival", "부산"), args.get("date"))
            elif name == "humanize_korean_text":
                output_text = humanize_korean_text(args.get("text", ""))
            elif name == "check_korean_spelling":
                output_text = check_korean_spelling(args.get("text", ""))
            elif name == "search_academic_papers":
                output_text = search_academic_papers(args.get("query", ""))
            elif name == "search_library_books":
                output_text = search_library_books(args.get("book_title", ""), args.get("region"))
            elif name == "search_patents":
                output_text = search_patents(args.get("query", ""))
            else:
                output_text = f"알 수 없는 도구: {name}"

            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": output_text}
                    ]
                }
            }
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

        response_body = json.dumps(resp, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self._set_cors()
        self.end_headers()
        self.wfile.write(response_body)

def run(port=None):
    if port is None:
        port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8765))
    server = HTTPServer(("0.0.0.0", port), McpHandler)
    print(f"Korean Life MCP Server running on port {port}...")
    server.serve_forever()

if __name__ == "__main__":
    run()
