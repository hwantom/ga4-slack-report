import json
import os
import sys
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    OrderBy,
    RunReportRequest,
)

# Windows 콘솔 한글 깨짐 방지
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def calculate_change(current: int, previous: int) -> dict:
    """어제와 전전날의 증감률을 계산하여 상세 정보를 딕셔너리로 반환합니다."""
    if previous == 0:
        if current == 0:
            rate = 0.0
            rate_str = "- 0.0%"
        else:
            rate = 100.0
            rate_str = "▲ 100.0%"
    else:
        diff = current - previous
        rate = (diff / previous) * 100
        if rate > 0:
            rate_str = f"▲ {rate:.1f}%"
        elif rate < 0:
            rate_str = f"▼ {abs(rate):.1f}%"
        else:
            rate_str = "- 0.0%"

    return {
        "current": current,
        "previous": previous,
        "rate": round(rate, 1),
        "rate_str": rate_str,
    }


def get_ga4_kpis(client: BetaAnalyticsDataClient, property_id: str) -> tuple[dict, dict]:
    """어제와 전전날의 4대 핵심 지표(activeUsers, sessions, screenPageViews, keyEvents)를 조회합니다."""
    def _fetch_single_day(date_str: str) -> dict:
        req = RunReportRequest(
            property=property_id,
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="screenPageViews"),
                Metric(name="keyEvents"),
            ],
            date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
        )
        res = client.run_report(req)
        vals = {
            "activeUsers": 0,
            "sessions": 0,
            "screenPageViews": 0,
            "keyEvents": 0,
        }
        if res.rows and res.rows[0].metric_values:
            mv = res.rows[0].metric_values
            vals["activeUsers"] = int(mv[0].value) if len(mv) > 0 else 0
            vals["sessions"] = int(mv[1].value) if len(mv) > 1 else 0
            vals["screenPageViews"] = int(mv[2].value) if len(mv) > 2 else 0
            vals["keyEvents"] = int(mv[3].value) if len(mv) > 3 else 0
        return vals

    yesterday_data = _fetch_single_day("yesterday")
    prev_data = _fetch_single_day("2daysAgo")
    return yesterday_data, prev_data


def get_recent_7days_trend(client: BetaAnalyticsDataClient, property_id: str) -> list[dict]:
    """최근 7일간(7daysAgo ~ yesterday) 일별 Users 및 Sessions 추이를 조회합니다."""
    req = RunReportRequest(
        property=property_id,
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
        date_ranges=[DateRange(start_date="7daysAgo", end_date="yesterday")],
        order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
    )
    res = client.run_report(req)
    trends = []
    for row in res.rows:
        raw_date = row.dimension_values[0].value  # YYYYMMDD
        formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date
        users = int(row.metric_values[0].value) if len(row.metric_values) > 0 else 0
        sessions = int(row.metric_values[1].value) if len(row.metric_values) > 1 else 0
        trends.append({
            "date": formatted_date,
            "users": users,
            "sessions": sessions,
        })
    return trends


def get_top_traffic_sources(client: BetaAnalyticsDataClient, property_id: str, limit: int = 5) -> list[dict]:
    """최근 7일간 상위 트래픽 유입 소스 TOP N을 조회합니다."""
    req = RunReportRequest(
        property=property_id,
        dimensions=[Dimension(name="sessionSource")],
        metrics=[Metric(name="sessions"), Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date="7daysAgo", end_date="yesterday")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=limit,
    )
    res = client.run_report(req)
    sources = []
    for row in res.rows:
        source_name = row.dimension_values[0].value or "(direct)"
        sessions = int(row.metric_values[0].value) if len(row.metric_values) > 0 else 0
        users = int(row.metric_values[1].value) if len(row.metric_values) > 1 else 0
        sources.append({
            "source": source_name,
            "sessions": sessions,
            "users": users,
        })
    return sources


def get_top_pages(client: BetaAnalyticsDataClient, property_id: str, limit: int = 5) -> list[dict]:
    """최근 7일간 상위 페이지 TOP N을 조회합니다."""
    req = RunReportRequest(
        property=property_id,
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date="7daysAgo", end_date="yesterday")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
        limit=limit,
    )
    res = client.run_report(req)
    pages = []
    for row in res.rows:
        page_path = row.dimension_values[0].value or "/"
        views = int(row.metric_values[0].value) if len(row.metric_values) > 0 else 0
        users = int(row.metric_values[1].value) if len(row.metric_values) > 1 else 0
        pages.append({
            "path": page_path,
            "views": views,
            "users": users,
        })
    return pages


def save_dashboard_data(
    yesterday_data: dict,
    changes: dict,
    trends_7d: list[dict],
    traffic_sources: list[dict],
    top_pages: list[dict],
    output_path: str = "dashboard/data.json",
) -> None:
    """대시보드에서 렌더링할 data.json 파일을 생성/갱신합니다."""
    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S (KST)")

    data = {
        "updated_at": now_kst,
        "kpi": {
            "users": yesterday_data.get("activeUsers", 0),
            "sessions": yesterday_data.get("sessions", 0),
            "page_views": yesterday_data.get("screenPageViews", 0),
            "key_events": yesterday_data.get("keyEvents", 0),
        },
        "changes": changes,
        "trends_7d": trends_7d,
        "traffic_sources": traffic_sources,
        "top_pages": top_pages,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"대시보드 데이터 저장 완료: {output_path}")


def format_slack_message(yesterday_data: dict, changes: dict, dashboard_url: str) -> dict:
    """Slack 메시지 페이로드를 구성합니다 (핵심 KPI + 대시보드 링크 버튼)."""
    users_val = yesterday_data.get("activeUsers", 0)
    users_rate = changes["users"]["rate_str"]

    sessions_val = yesterday_data.get("sessions", 0)
    sessions_rate = changes["sessions"]["rate_str"]

    views_val = yesterday_data.get("screenPageViews", 0)
    views_rate = changes["page_views"]["rate_str"]

    events_val = yesterday_data.get("keyEvents", 0)
    events_rate = changes["key_events"]["rate_str"]

    fallback_text = (
        "📊 Daily GA4 Report\n\n"
        f"👥 Users: {users_val:,}  {users_rate}\n"
        f"🔄 Sessions: {sessions_val:,}  {sessions_rate}\n"
        f"👀 Page Views: {views_val:,}  {views_rate}\n"
        f"🎯 Key Events: {events_val:,}  {events_rate}\n\n"
        f"전체 대시보드: {dashboard_url}"
    )

    kpi_block_text = (
        f"*👥 Users*\n{users_val:,}  {users_rate}\n\n"
        f"*🔄 Sessions*\n{sessions_val:,}  {sessions_rate}\n\n"
        f"*👀 Page Views*\n{views_val:,}  {views_rate}\n\n"
        f"*🎯 Key Events*\n{events_val:,}  {events_rate}"
    )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Daily GA4 Report",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": kpi_block_text,
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 전체 대시보드 보기",
                        "emoji": True,
                    },
                    "url": dashboard_url,
                    "style": "primary",
                }
            ],
        },
    ]

    return {
        "text": fallback_text,
        "blocks": blocks,
    }


def send_slack_message(webhook_url: str, payload: dict) -> None:
    """Slack Incoming Webhook으로 Block Kit 메시지를 전송합니다."""
    response = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    print(f"Slack 응답 상태 코드: {response.status_code}")
    print(f"Slack 응답 본문: {response.text.strip()}")
    response.raise_for_status()
    print("Slack 메시지 전송 성공!")


def main():
    # 1. 환경변수 로드
    load_dotenv()

    property_id = os.getenv("GA4_PROPERTY_ID", "").strip()
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json").strip()
    dashboard_url = os.getenv("DASHBOARD_URL", "https://tom.github.io/ga4-slack-report/").strip()

    # 2. 유효성 검증
    errors = []
    if not property_id:
        errors.append("GA4_PROPERTY_ID가 .env 파일에 설정되지 않았습니다.")
    if not webhook_url:
        errors.append("SLACK_WEBHOOK_URL이 .env 파일에 설정되지 않았습니다.")
    if not os.path.exists(credentials_path):
        errors.append(f"서비스 계정 키 파일 '{credentials_path}'이(가) 존재하지 않습니다.")

    if errors:
        print("[설정 오류]")
        for err in errors:
            print(f"- {err}")
        print("\n.env 파일과 서비스 계정 키 파일을 확인한 후 다시 실행해주세요.")
        sys.exit(1)

    if not property_id.startswith("properties/"):
        formatted_property_id = f"properties/{property_id}"
    else:
        formatted_property_id = property_id

    # 3. Google Analytics Data API 클라이언트 생성
    try:
        client = BetaAnalyticsDataClient.from_service_account_file(credentials_path)
    except Exception as e:
        print(f"서비스 계정 인증 실패: {e}")
        sys.exit(1)

    # 4. GA4 데이터 수집
    print("GA4 데이터 수집 중...")
    try:
        yesterday_data, prev_data = get_ga4_kpis(client, formatted_property_id)
        trends_7d = get_recent_7days_trend(client, formatted_property_id)
        traffic_sources = get_top_traffic_sources(client, formatted_property_id, limit=5)
        top_pages = get_top_pages(client, formatted_property_id, limit=5)
    except Exception as e:
        print(f"GA4 데이터 조회 실패: {e}")
        sys.exit(1)

    # 5. 증감률 계산
    changes = {
        "users": calculate_change(yesterday_data.get("activeUsers", 0), prev_data.get("activeUsers", 0)),
        "sessions": calculate_change(yesterday_data.get("sessions", 0), prev_data.get("sessions", 0)),
        "page_views": calculate_change(yesterday_data.get("screenPageViews", 0), prev_data.get("screenPageViews", 0)),
        "key_events": calculate_change(yesterday_data.get("keyEvents", 0), prev_data.get("keyEvents", 0)),
    }

    # 6. dashboard/data.json 저장
    save_dashboard_data(
        yesterday_data=yesterday_data,
        changes=changes,
        trends_7d=trends_7d,
        traffic_sources=traffic_sources,
        top_pages=top_pages,
        output_path="dashboard/data.json",
    )

    # 7. Slack 메시지 구성 및 전송
    slack_payload = format_slack_message(yesterday_data, changes, dashboard_url)
    print("\n[Slack 전송 페이로드 요약]")
    print(slack_payload["text"])
    print()

    print("Slack으로 전송 중...")
    try:
        send_slack_message(webhook_url, slack_payload)
    except Exception as e:
        print(f"Slack 전송 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
