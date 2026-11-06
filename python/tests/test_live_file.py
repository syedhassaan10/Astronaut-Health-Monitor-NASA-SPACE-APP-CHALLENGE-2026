"""Live logbook file: every rep is added to a CSV on disk as it happens."""

import threading

from data.logbook_csv import parse_logbook_csv
from db.live_file import LiveFile
from db.repo import rep_id
from db.schema import RepRow


def rep(rep_no):
    return RepRow(id=rep_id("s1", rep_no), session_id="s1", crew_id="c1", exercise="squat",
                  timestamp=1_000_000 + rep_no * 1000, gravity_g=0, target_load_kg=110, rep_no=rep_no,
                  min_knee_angle=95, eccentric_s=3, concentric_s=1, asymmetry=2, confidence=0.9, form_score=90,
                  flags=["shallow"], level="amber")


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def test_new_file_gets_the_header_then_every_rep_in_order(tmp_path):
    path = tmp_path / "logbook.csv"
    live = LiveFile()
    live.use(path)
    live.append_rep(rep(1))
    live.append_rep(rep(2))
    parsed = parse_logbook_csv(read(path))
    assert [r.rep_no for r in parsed.reps] == [1, 2]
    assert parsed.reps[0].min_knee_angle == 95
    assert (live.status.file_name, live.status.reps_written, live.status.error) == ("logbook.csv", 2, None)


def test_an_existing_file_keeps_its_content_and_gets_no_second_header(tmp_path):
    path = tmp_path / "logbook.csv"
    live = LiveFile()
    live.use(path)
    live.append_rep(rep(1))
    live.stop()
    live.use(path)
    live.append_rep(rep(2))
    text = read(path)
    assert text.count("record,id") == 1
    assert len(parse_logbook_csv(text).reps) == 2


def test_reps_written_from_several_threads_all_arrive(tmp_path):
    path = tmp_path / "logbook.csv"
    live = LiveFile()
    live.use(path)
    threads = [threading.Thread(target=live.append_rep, args=(rep(i),)) for i in range(1, 21)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    numbers = sorted(r.rep_no for r in parse_logbook_csv(read(path)).reps)
    assert numbers == list(range(1, 21))
    assert live.status.reps_written == 20


def test_does_nothing_when_no_file_is_chosen():
    live = LiveFile()
    live.append_rep(rep(1))
    assert live.status.reps_written == 0


def test_a_failed_write_is_shown_and_never_raises(tmp_path):
    path = tmp_path / "logbook.csv"
    live = LiveFile()
    live.use(path)
    path.unlink()
    path.mkdir()  # the file is now a folder, so writing fails
    live.append_rep(rep(1))
    assert live.status.error is not None
    assert live.status.reps_written == 0


def test_the_live_file_imports_like_an_export(tmp_path):
    path = tmp_path / "logbook.csv"
    live = LiveFile()
    live.use(path)
    for i in range(1, 4):
        live.append_rep(rep(i))
    parsed = parse_logbook_csv(read(path))
    assert parsed.errors == []
    assert parsed.total_rows == 3
