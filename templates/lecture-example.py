"""Slides and narration of the part 1 lecture (book part 1: chapters 1 and 2).

Each slide is an HTML fragment for a 1920 x 1080 frame. Elements with a
data-s="N" attribute appear from step N of that slide on, and steps[N - 1]
is the narration spoken while step N is on screen. Every fact comes from
book/part1.md, book/ch01-ai-workloads.md or book/ch02-architecture.md, and
the section is noted next to each narration step.
"""

from .common import AMBER, GREEN, NAVY, bookfig, card, code, flow, note, stat, table, title_slide

NAME = "3fs-lecture-part1"
KICKER = "3FS 구조 · 1부 강의"

SLIDES = []


def place(fragment, left, width):
    """Put a component that common.py places at left:120px at another x with a fixed width."""
    return fragment.replace('style="', f'style="left:{left}px;width:{width}px;', 1)


def question(label, text, top=240, s=1):
    return (f'<div class="callout" data-s="{s}" style="top:{top}px;background:#F1F6F9;border-left-color:{NAVY};'
            f'font-size:36px;padding:24px 36px"><b style="color:{NAVY}">{label}</b>&nbsp; {text}</div>')


def side_list(items, left, top, size=32, width=None):
    """A bullet list at an arbitrary x. Items are (text, subtext, step)."""
    w = f"width:{width}px;right:auto;" if width else ""
    lis = "".join(f'<li data-s="{st}">{t}<span class="sub">{sub}</span></li>' for t, sub, st in items)
    return f'<ul class="pts" style="left:{left}px;{w}top:{top}px;font-size:{size}px">{lis}</ul>'


# 1. Title ------------------------------------------------------------------
SLIDES.append(title_slide(
    "1부 강의", "문제와 지도", "1장 · 2장", "책 『3FS 구조』 1부 (1~2장)",
    steps=[
        "1부에서는 AI 학습과 추론이 스토리지에 무엇을 요구하고, 3FS가 어떤 구조로 그 요구를 채우는지 살펴봅니다.",  # part1.md
        "1장에서 요구를 정리하고, 2장에서 설계 결정과 책 전체가 쓰는 예제 클러스터를 정합니다.",  # part1.md
    ]))

# 2. Workloads (1.1) ----------------------------------------------------------
SLIDES.append(dict(
    title="AI 워크로드의 데이터 접근",
    html=question("1장의 질문", "학습 작업 하나가 클러스터 전체 SSD의 대역폭을 합쳐 쓰려면 스토리지는 무엇을 해야 하는가")
    + table(["접근", "요청 하나의 크기", "동시성", "느려지면"], [
        ["데이터셋 무작위 읽기", "샘플 하나 150KB~140MB", "모든 학습 노드가 쉬지 않고", "가속기가 기다린다"],
        ["체크포인트 쓰기", "프로세스 8개 몫 99~144GiB", "몇 분마다 모든 노드가 한꺼번에", "학습이 멈추거나<br>저장 간격이 는다"],
        ["KVCache 읽기", "32,768토큰이면 수 GB", "추론 노드마다", "첫 응답이 늦어진다"],
    ], top=420, widths=["22%", "27%", "29%", "22%"], size=30)
    + f'<div class="callout" data-s="2" style="top:850px;font-size:36px;padding:22px 36px">'
      f'많은 노드가 동시에 큰 양을 다루고, 쓴 노드와 읽는 노드가 다르다</div>',
    steps=[
        "1장의 질문은 작업 하나가 전체 SSD의 대역폭을 합쳐 쓰려면 스토리지가 무엇을 해야 하는가입니다. 학습은 샘플을 무작위로 읽고, 몇 분마다 모든 노드가 체크포인트를 한꺼번에 씁니다.",  # 1장 핵심 질문, 1.1절 표 1.4
        "추론 서버는 앞부분이 32,768토큰이면 수 기가바이트인 KVCache를 읽습니다. 세 접근 모두 많은 노드가 동시에 큰 양을 다루고, 쓴 노드와 읽는 노드가 다릅니다.",  # 1.1절 표 1.3, 표 1.4
    ]))

# 3. Scale (1.2) --------------------------------------------------------------
sub = "<br><span style='font-size:28px;color:#5B6B78'>{}</span>"
SLIDES.append(dict(
    title="공개 클러스터의 규모",
    html=stat(120, "2,880", "SSD" + sub.format("스토리지 노드 180대 × 16"), top=240)
    + stat(690, "6.6", "집계 읽기 처리량" + sub.format("3FS README 측정"), unit="TiB/s", top=240)
    + stat(1260, "2.3", "SSD 하나의 평균" + sub.format("6.6 TiB/s ÷ 2,880"), unit="GiB/s", top=240)
    + place(table(["값", "계산", "결과"], [
        ["스토리지 NIC 합계 대비", "6.6 ÷ 8.19 TiB/s", "약 81%"],
        ["512KiB 읽기의 수", "6.6 TiB/s ÷ 512KiB", "초당 약 1,384만 건"],
    ], top=650, s=2, widths=["36%", "36%", "28%"], num_cols=(2,), size=30), 120, 1680)
    + note("데이터 경로에 메타데이터 조회가 끼면 그 서버도 초당 1,384만 건을 받는다", y=900, s=2),
    steps=[
        "공개된 측정에서 SSD 2,880개가 초당 약 6.6 테비바이트를 읽었습니다. SSD 하나가 평균 초당 2.3 기비바이트를 낸 셈입니다.",  # 1.2절 표 1.5
        "512키비바이트 읽기로 치면 초당 약 1,384만 건이므로, 이 경로에 메타데이터 서버 조회가 끼면 그 서버도 같은 수의 요청을 받습니다.",  # 1.2절, 설계 교훈 1.1
    ]))

# 4. Existing approaches (1.3) -------------------------------------------------
SLIDES.append(dict(
    title="기존 방식의 한계",
    html=bookfig("fig-1-4-approaches.drawio.svg", 90, 235, w=940)
    + side_list([
        ("<b>(a) 로컬 디스크 복사</b>", "샤드로 나누면 다음 샘플이 그 노드에 있을 확률 0.08% (노드 약 1,250대)", 1),
        ("<b>(b) HPC 병렬 파일 시스템</b>", "기본 구성은 조각마다 서버 하나만 읽기를 받아 사본으로 대역폭을 늘리지 못한다", 1),
        ("<b>(c) 객체 저장소와 캐시</b>", "디렉터리 rename이 원자적이지 않고, 캐시는 TTL 동안 낡은 값을 보일 수 있다", 1),
    ], left=1080, top=250, size=34),
    steps=[
        "데이터셋을 노드마다 나눠 복사하면 다음 샘플이 그 노드에 있을 확률이 0.08퍼센트이고, 병렬 파일 시스템은 기본 구성에서 사본으로 읽기 대역폭을 늘리지 못하며, 객체 저장소는 디렉터리 rename이 원자적이지 않습니다.",  # 1.3절 표 1.6, 표 1.7
    ]))

# 5. Requirements (1.4) --------------------------------------------------------
ans = "<div style='position:absolute;left:40px;right:40px;bottom:36px;font-size:28px;color:#5B6B78'>3FS의 답<br>{}</div>"
SLIDES.append(dict(
    title="스토리지 요구 사항",
    html=card(120, 250, 540, 600, "요구 1 대역폭 집계",
              "작업 하나가 전체 SSD와 NIC의 대역폭을 합쳐 쓴다<br><span class='cost'>SSD가 고장 난 동안에도</span>"
              + ans.format("분산 배치, 위치 계산,<br>모든 사본에서 읽기"), 1)
    + card(690, 250, 540, 600, "요구 2 강한 일관성",
           "쓰기 완료 응답 뒤에 시작한 읽기는 어느 사본에서 읽든 그 쓰기의 결과를 본다"
           + ans.format("CRAQ 복제,<br>메타데이터 트랜잭션"), 2, AMBER)
    + card(1260, 250, 540, 600, "요구 3 파일 인터페이스",
           "디렉터리, 원자적 rename, 링크를 그대로 쓴다<br><span class='cost'>성능이 중요한 응용에는<br>대역폭을 잃지 않는 경로</span>"
           + ans.format("FoundationDB 위의 meta,<br>FUSE와 USRBIO"), 3, GREEN),
    steps=[
        "요구 1은 대역폭 집계입니다. 작업 하나가 전체 SSD와 NIC의 대역폭을 합쳐 쓰고, 고장 중에도 그 대역폭을 크게 잃지 않아야 합니다.",  # 1.4절 요구 1
        "요구 2는 강한 일관성입니다. 쓰기 완료 응답 뒤에 시작한 읽기는 어느 사본에서 읽든 그 쓰기의 결과를 보아야 합니다.",  # 1.4절 요구 2
        "요구 3은 파일 인터페이스입니다. 응용은 POSIX 인터페이스를 그대로 쓰고, 성능이 중요한 응용에는 대역폭을 잃지 않는 경로가 있어야 합니다.",  # 1.4절 요구 3
    ]))

# 6. Events 1 and 2 (1.5) ------------------------------------------------------
SLIDES.append(dict(
    title="사건 1과 사건 2의 계산",
    html=bookfig("fig-1-5-read-replicas.drawio.svg", 90, 250, w=1000)
    + note("<b>사건 1</b> 512KiB 읽기 → 청크 5, 6 → 체인 2개, 후보 사본 6개 (노드 4대)", x=120, y=905)
    + card(1140, 250, 660, 600, "사건 2 체크포인트 쓰기",
           "step-1000.pt에 16MiB<br>청크 16개 → 체인 16개<br>타깃 쓰기 16 × 3 = 48번<br>SSD에 쓰는 양 48MiB"
           "<br><span class='cost'>gpu1이 보내는 양 16MiB,<br>storage 사이 전달 32MiB</span>", 2, AMBER),
    steps=[
        "예제 클러스터의 사건 1에서 gpu1이 오프셋 5.75메비바이트부터 512키비바이트를 읽으면, 읽기는 청크 5와 6으로 나뉘고 후보 사본은 노드 4대의 6개입니다.",  # 1.5절 표 1.9, 그림 1.5
        "사건 2에서 체크포인트 파일에 16메비바이트를 쓰면 청크 16개가 체인 16개로 퍼지고, 타깃 쓰기 48번으로 SSD에 48메비바이트가 쓰입니다.",  # 1.5절 표 1.10
    ]))

# 7. Design decisions (2.1) ----------------------------------------------------
lab = "<span style='font:700 26px \"Noto Sans CJK KR\";color:#8A97A3'>결정 {}</span><br>"
SLIDES.append(dict(
    title="3FS의 설계 결정",
    html=question("2장의 질문", "3FS는 어떤 결정으로 1장의 요구를 푸는가")
    + flow([
        (lab.format(1) + "청크 분산 배치", "파일을 청크로 잘라 여러 체인에 번갈아 놓는다<br><br>운영 환경: 파일 하나에 체인 200개"),
        (lab.format(2) + "위치 조회 대신 계산", "파일을 열 때 받은 레이아웃으로 청크의 체인을 계산한다<br><br>파일을 연 뒤의 I/O에서 메타데이터 서버가 빠진다"),
        (lab.format(3) + "메타데이터의 외부 위임", "메타데이터를 트랜잭션 키값 저장소 FoundationDB에 저장한다"),
    ], top=420, step_each=True, height=400),
    steps=[
        "2장의 질문은 3FS가 어떤 결정으로 이 요구를 푸는가입니다. 결정 1로 3FS는 파일을 청크로 잘라 여러 체인에 번갈아 놓습니다.",  # 2장 핵심 질문, 2.1절 결정 1
        "결정 2로 클라이언트는 파일을 열 때 받은 레이아웃에서 청크의 체인을 계산하므로, 그 뒤의 읽기와 쓰기에서 메타데이터 서버가 빠집니다.",  # 2.1절 결정 2, 설계 교훈 2.1
        "결정 3으로 3FS는 분산 트랜잭션을 직접 구현하지 않고, 메타데이터를 FoundationDB라는 트랜잭션 키값 저장소에 맡깁니다.",  # 2.1절 결정 3
    ]))

# 8. Components (2.2) ----------------------------------------------------------
SLIDES.append(dict(
    title="구성 요소와 역할",
    html=bookfig("fig-2-1-components.drawio.svg", 90, 228, w=830)
    + place(table(["프로세스", "하는 일"], [
        ["mgmtd", "멤버십, 하트비트 검사, 라우팅 정보"],
        ["meta", "파일 시스템 의미, inode, 레이아웃"],
        ["storage", "청크 저장, CRAQ 복제"],
        ["FUSE 클라이언트", "마운트 지점, USRBIO"],
        ["monitor_collector", "메트릭 수집"],
    ], top=240, widths=["38%", "62%"], size=28), 970, 830)
    + f'<div class="callout" data-s="2" style="left:970px;top:730px;font-size:32px;padding:24px 32px">'
      f'청크 데이터: 클라이언트와 storage 사이 RDMA<br>meta: 조회, 생성, 닫기<br>mgmtd: 라우팅 정보 10초마다</div>',
    steps=[
        "mgmtd는 멤버십과 라우팅 정보를, meta는 파일 시스템 의미와 레이아웃을, storage는 청크 저장과 CRAQ 복제를, FUSE 클라이언트는 마운트 지점과 USRBIO를 맡습니다.",  # 2.2절 프로세스 표
        "청크 데이터는 클라이언트와 storage 사이를 RDMA로 오가며 meta와 mgmtd를 지나지 않습니다. 클라이언트는 10초마다 mgmtd에서 라우팅 정보를 받습니다.",  # 2.2절 그림 2.1
    ]))

# 9. Example cluster (2.3) -----------------------------------------------------
SLIDES.append(dict(
    title="예제 클러스터",
    html=bookfig("fig-2-2-cluster.drawio.svg", 90, 240, w=900)
    + f'<div class="note" style="left:1050px;top:250px;font-size:34px;color:#1B1B1B"><b style="color:{NAVY}">노드 7대</b><br>'
      f'meta 1대, storage 5대 (SSD 16개씩),<br>gpu1 1대</div>'
    + place(table(["값", "계산", "결과"], [
        ["타깃", "5 × 16 × 6", "480"],
        ["체인", "480 ÷ 3", "160"],
        ["노드 하나의 체인", "16 × 6", "96 (60%)"],
        ["쓸 수 있는 용량", "1,120TB ÷ 3", "약 373TB"],
    ], top=480, s=2, widths=["40%", "32%", "28%"], num_cols=(2,), size=30), 1050, 750),
    steps=[
        "예제 클러스터는 meta 노드 1대와 SSD를 16개씩 둔 storage 노드 5대, 학습 프로세스가 실행되는 gpu1로 이루어진 노드 7대입니다.",  # 2.3절 노드 표
        "타깃은 480개, 체인은 160개입니다. 노드 하나가 체인 96개에 속하므로, 노드 하나가 멈추면 체인의 60퍼센트가 사본 하나를 잃습니다.",  # 2.3절 표
    ]))

# 10. Chunk location (2.4) -----------------------------------------------------
SLIDES.append(dict(
    title="청크 위치 계산",
    html=code("[[c:// 데이터셋 파일의 레이아웃 (inode에 저장, 시작 인덱스와 시드는 책의 가정)]]\n"
              "chunkSize = 1MiB, stripeSize = 16\n"
              "chains = ChainRange{baseIndex = 17, shuffle = STD_SHUFFLE_MT19937, seed = 1}", top=240, size=32)
    + flow([
        ("청크 5", "5.75MiB ÷ 1MiB의 몫"),
        ("위치 5", "5 mod 16"),
        ("체인 인덱스 20", "섞은 목록의 위치 5"),
        ("체인 900200010", "storage3 → 4 → 5<br>2번 SSD"),
    ], top=480, s=2, height=210)
    + f'<div class="callout" data-s="2" style="top:770px">청크 64개의 위치는 어디에도 기록되어 있지 않다 <span class="arrow">·</span> 네트워크 왕복 0번</div>',
    steps=[
        "파일을 만들 때 meta는 연속한 체인 인덱스 16개를 시드로 섞고, 레이아웃에는 섞은 목록 대신 시작 인덱스 17과 시드 1을 저장합니다.",  # 2.4절 규칙 1, 2
        "오프셋 5.75메비바이트는 청크 5이고, 5를 16으로 나눈 나머지인 위치 5에 체인 인덱스 20이 있습니다. 청크의 위치는 어디에도 기록되지 않고, 계산에는 네트워크 왕복이 없습니다.",  # 2.4절 규칙 3, 불변식 2.1
    ]))

# 11. Read and write paths (2.5, 2.6) -----------------------------------------
row = "<div class='note' data-s='{s}' style='left:120px;top:{y}px;font-weight:700;color:{c}'>{t}</div>"
SLIDES.append(dict(
    title="읽기와 쓰기 경로",
    html=row.format(s=1, y=240, c=NAVY, t="사건 1 읽기 (청크 5, 6)")
    + flow([
        ("경로 조회", "meta가 레이아웃이 든<br>inode를 준다"),
        ("청크 분할", "청크 경계에서 자르고<br>체인을 계산한다"),
        ("사본 선택", "체인마다<br>타깃 하나"),
        ("RDMA WRITE", "storage가 gpu1<br>버퍼에 직접 쓴다"),
    ], top=290, s=1, height=210)
    + row.format(s=2, y=560, c="#B9802A", t="사건 2 쓰기 (청크 0, 체인 900400003)")
    + flow([
        ("파일 생성", "meta가 inode와 세션을<br>트랜잭션 하나로"),
        ("머리로", "storage1이<br>RDMA READ로 당긴다"),
        ("전파", "storage1 → storage2<br>→ storage5"),
        ("커밋", "꼬리에서 커밋,<br>응답은 거꾸로"),
    ], top=610, s=2, height=210)
    + note("meta가 끼는 곳: 경로 조회, 생성, 닫기 &nbsp;·&nbsp; 타깃 쓰기 48번은 모두 클라이언트와 storage 사이", y=880, s=2),
    steps=[
        "사건 1에서 FUSE 클라이언트는 경로 조회 때 받은 레이아웃으로 체인마다 타깃 하나를 고르고, 그 storage가 RDMA WRITE로 gpu1의 버퍼에 직접 씁니다.",  # 2.5절 그림 2.4
        "사건 2의 청크 0은 머리인 storage1에서 꼬리인 storage5까지 전해지고, 꼬리에서 커밋된 뒤 응답이 거꾸로 돌아옵니다.",  # 2.6절 그림 2.5
    ]))


# 12. Event 3 (2.7) -------------------------------------------------------------
def tl_events(events, s, start):
    """Timeline events of one step. start keeps the above/below alternation across calls."""
    parts = []
    for i, (pos, t, d) in enumerate(events):
        alt = " alt" if (start + i) % 2 else ""
        parts.append(f'<div class="ev{alt}" data-s="{s}" style="left:{100 * pos:.1f}%"><div class="dot"></div>'
                     f'<div class="t">{t}</div><div class="d" style="width:340px;left:-170px">{d}</div></div>')
    return "".join(parts)


SLIDES.append(dict(
    title="사건 3의 장애 처리",
    html='<div class="tl" style="top:300px"><div class="axis"></div>'
    + tl_events([
        (0.04, "t = 0", "storage3의 프로세스가<br>멈춘다"),
        (0.27, "60~70초", "10초마다 하는 검사가<br>장애로 판정한다"),
    ], 1, 0)
    + tl_events([
        (0.50, "판정 직후", "체인 96개에서<br>storage3 타깃을 끝으로"),
        (0.73, "최대 81초", "storage2가 새 체인을 보고<br>쓰기를 끝낸다"),
        (0.95, "재시작 뒤", "밀린 청크를 따라잡은 뒤<br>다시 읽기에 들어간다"),
    ], 2, 2)
    + "</div>"
    + f'<div class="callout" data-s="2" style="top:740px;font-size:36px">최대 81초 = 판정 70초 + 체인 저장 1초 + 라우팅 정보 주기 10초</div>',
    steps=[
        "사건 3에서는 사건 2의 쓰기 도중 storage3의 프로세스가 멈춥니다. mgmtd는 하트비트가 60초 동안 끊긴 노드를 10초마다 하는 검사에서 장애로 판정합니다.",  # 2.7절
        "판정 뒤 storage3의 타깃은 체인 끝으로 옮겨지고, 다른 노드가 새 체인을 받기까지 최대 81초가 걸립니다. 다시 시작한 타깃은 밀린 청크를 따라잡은 뒤에야 읽기에 들어갑니다.",  # 2.7절 표, 그림 2.6
    ]))

# 13. Summary -------------------------------------------------------------------
SLIDES.append(dict(
    title="1부 정리",
    html=side_list([
        ("<b>요구</b>", "작업 하나가 전체 SSD의 대역폭을 합쳐 쓰고, 응용은 데이터가 어느 기계에 있는지 몰라도 된다", 1),
        ("<b>3FS의 답</b>", "청크 분산 배치, 위치 계산, FoundationDB에 메타데이터 위임", 1),
        ("<b>예제 클러스터</b>", "노드 7대, 타깃 480개, 체인 160개에서 사건 1~3을 뒤의 장마다 다시 따라간다", 2),
    ], left=120, top=250, size=40)
    + f'<div class="callout" data-s="2" style="top:800px"><b>다음: 2부 토대</b> <span class="arrow">·</span> 실행 모델, RPC와 직렬화, RDMA 전송</div>',
    steps=[
        "3FS는 작업 하나가 전체 SSD의 대역폭을 합쳐 쓰면서도 응용은 데이터의 위치를 몰라도 되도록, 청크를 흩어 놓고 위치를 계산하며 메타데이터를 FoundationDB에 맡깁니다.",  # 1.4절, 2.11절
        "뒤의 장들은 같은 사건 1부터 3까지를 다시 따라갑니다. 2부에서는 모든 서비스가 함께 쓰는 실행 모델과 RPC, RDMA 전송을 봅니다.",  # part1.md, part2.md
    ]))

# Wrap Korean text at word boundaries. The wrapper is static, so absolutely placed children
# still position against .frame.
for _slide in SLIDES:
    _slide["html"] = f'<div style="word-break:keep-all">{_slide["html"]}</div>'
