from lmsal_links import event_links

SNAPSHOT = 'https://www.lmsal.com/solarsoft/ssw/last_events-2026/last_events_20260705_1201/index.html'
OLD_SNAPSHOT = 'https://www.lmsal.com/solarsoft/ssw/last_events-2002/last_events_20021218_0957/index.html'


def test_absolute_link_as_lmsal_writes_it_upgraded_to_https():
    html = '<TD><A HREF="http://www.lmsal.com/solarsoft/latest_events_archive/events_summary/2026/07/04/gev_20260704_2029/index.html">gev_20260704_2029</A></TD>'
    assert event_links(html, SNAPSHOT) == {
        'gev_20260704_2029': 'https://www.lmsal.com/solarsoft/latest_events_archive/events_summary/2026/07/04/gev_20260704_2029/index.html'}


def test_relative_link_on_old_pages_resolves_against_the_snapshot():
    html = '<td><a href="gev_20021214_1158.html">gev_20021214_1158</a></td>'
    assert event_links(html, OLD_SNAPSHOT) == {
        'gev_20021214_1158': 'https://www.lmsal.com/solarsoft/ssw/last_events-2002/last_events_20021218_0957/gev_20021214_1158.html'}


def test_first_link_per_event_wins_and_other_links_are_ignored():
    html = ('<a href="index.html">home</a>'
            '<a href="gev_20021214_1158.html">gev_20021214_1158</a>'
            '<a href="gev_20021214_1158_thumb.png">img</a>')
    assert list(event_links(html, OLD_SNAPSHOT).values()) == [
        'https://www.lmsal.com/solarsoft/ssw/last_events-2002/last_events_20021218_0957/gev_20021214_1158.html']


def test_backfill_reads_each_snapshot_once_and_skips_events_that_have_a_link():
    events = [
        {'event_id': 'gev_20021214_1158', 'seen_in_dates': [OLD_SNAPSHOT]},
        {'event_id': 'gev_20021214_1300', 'seen_in_dates': [OLD_SNAPSHOT]},
        {'event_id': 'gev_20260704_2029', 'seen_in_dates': [SNAPSHOT], 'event_url': 'https://kept'},
    ]
    fetched = []
    page = '<a href="gev_20021214_1158.html">x</a><a href="gev_20021214_1300.html">y</a>'
    from lmsal_links import backfill
    assert backfill(events, lambda url: fetched.append(url) or page, pause=0) == 2
    assert fetched == [OLD_SNAPSHOT]
    assert events[1]['event_url'].endswith('/gev_20021214_1300.html') and events[2]['event_url'] == 'https://kept'
