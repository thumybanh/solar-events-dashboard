from dedupe_lmsal import merge_duplicates

SNAP = 'https://www.lmsal.com/solarsoft/ssw/last_events-2026/last_events_{}/index.html'


def E(id, start, stop, peak, cls, pos, snaps):
    return {'event_id': id, 'event_start': start, 'event_stop': stop, 'event_peak': peak, 'event_GOES': cls,
            'event_position': pos, 'seen_in_dates': [SNAP.format(s) for s in snaps],
            'event_url': f'https://lmsal/{id}'}


def by_id(events):
    return {e['event_id']: e for e in events}


def test_screenshot_pair_listed_together_keeps_the_earlier_start_and_the_ar_number():
    events = [
        E('gev_20261001_2121', '2026/10/01 21:21:00', '21:56:16', '21:37:00', 'C1.5', 'N22E64',
          ['20261001_2358', '20261002_1201', '20261004_0001']),
        E('gev_20261001_2120', '2026/10/01 21:20:00', '21:58:00', '21:37:00', 'C1.5', 'N22E64( 4545 )',
          ['20261002_1201', '20261004_0001']),
    ]
    out = merge_duplicates(events)
    assert [e['event_id'] for e in out] == ['gev_20261001_2120']
    kept = out[0]
    assert kept['event_position'] == 'N22E64( 4545 )'
    assert [m['event_id'] for m in kept['merged_from']] == ['gev_20261001_2121']
    dropped = kept['merged_from'][0]
    assert (dropped['event_start'], dropped['event_stop'], dropped['event_url']) == (
        '2026/10/01 21:21:00', '21:56:16', 'https://lmsal/gev_20261001_2121')
    assert len(dropped['seen_in_dates']) == 3  # that entry's own snapshot history is kept


def test_ar_number_is_copied_when_only_the_dropped_entry_has_it():
    events = [
        E('gev_20261001_2120', '2026/10/01 21:20:00', '21:58:00', '21:37:00', 'C1.5', 'N22E64', ['20261004_0001']),
        E('gev_20261001_2121', '2026/10/01 21:21:00', '21:56:16', '21:37:00', 'C1.5', 'N22E64( 4545 )', ['20261004_0001']),
    ]
    assert merge_duplicates(events)[0]['event_position'] == 'N22E64( 4545 )'


def test_replaced_entry_keeps_lmsal_latest_version():
    # LMSAL listed 0104 until 04-12, then only 0146 from 04-13: 0146 is its correction
    events = [
        E('gev_20200407_0104', '2020/04/07 01:04:00', '02:21:00', '01:59:00', 'B1.0', 'N05W10',
          ['20200407_1202', '20200412_1202']),
        E('gev_20200407_0146', '2020/04/07 01:46:00', '02:26:00', '01:59:00', 'B1.0', 'N05W10', ['20200413_1202']),
    ]
    assert [e['event_id'] for e in merge_duplicates(events)] == ['gev_20200407_0146']


def test_three_entries_become_one_even_across_midnight():
    events = [
        E('gev_20210411_1928', '2021/04/11 19:28:00', '20:04:00', '01:33:00', 'A3.9', 'S23E20', ['20210412_1200']),
        E('gev_20210411_2040', '2021/04/11 20:40:00', '22:06:00', '01:33:00', 'A3.9', 'S23E20', ['20210412_1200']),
        E('gev_20210412_0127', '2021/04/12 01:27:00', '01:39:00', '01:33:00', 'A3.9', 'S23E20( 2814 )', ['20210412_1200']),
    ]
    out = merge_duplicates(events)
    assert len(out) == 1 and out[0]['event_id'] == 'gev_20210411_1928'
    assert out[0]['event_position'] == 'S23E20( 2814 )'
    assert sorted(m['event_id'] for m in out[0]['merged_from']) == ['gev_20210411_2040', 'gev_20210412_0127']


def test_different_peak_class_or_position_are_not_merged():
    base = dict(start='2023/05/26 00:58:00', stop='02:02:00', snaps=['20230527_0000'])
    events = [
        E('gev_20230526_0058', base['start'], base['stop'], '01:35:00', 'C1.3', 'S18E19( 3315 )', base['snaps']),
        E('gev_20230526_0102', '2023/05/26 01:02:00', '01:43:53', '01:22:00', 'C1.3', 'S18E19( 3315 )', base['snaps']),  # peak differs
        E('gev_20230526_0059', '2023/05/26 00:59:00', '02:00:00', '01:35:00', 'C1.4', 'S18E19( 3315 )', base['snaps']),  # class differs
        E('gev_20230526_0100', '2023/05/26 01:00:00', '02:00:00', '01:35:00', 'C1.3', 'S19E19( 3315 )', base['snaps']),  # position differs
    ]
    out = merge_duplicates(events)
    assert len(out) == 4 and all('merged_from' not in e for e in out)


def test_running_again_changes_nothing_and_keeps_the_merged_record_sticky():
    events = [
        E('gev_20261001_2121', '2026/10/01 21:21:00', '21:56:16', '21:37:00', 'C1.5', 'N22E64', ['20261004_0001']),
        E('gev_20261001_2120', '2026/10/01 21:20:00', '21:58:00', '21:37:00', 'C1.5', 'N22E64( 4545 )', ['20261004_0001']),
    ]
    once = merge_duplicates(events)
    assert merge_duplicates(once) == once
    # the scraper re-adds the dropped entry, seen in a newer snapshot: it rejoins the same record
    readded = E('gev_20261001_2121', '2026/10/01 21:21:00', '21:56:16', '21:37:00', 'C1.5', 'N22E64', ['20261005_0001'])
    again = merge_duplicates(once + [readded])
    assert [e['event_id'] for e in again] == ['gev_20261001_2120']
    entry = again[0]['merged_from'][0]
    assert [m['event_id'] for m in again[0]['merged_from']] == ['gev_20261001_2121']
    assert entry['seen_in_dates'][-1].endswith('20261005_0001/index.html')


def test_events_without_duplicates_are_returned_unchanged_and_in_order():
    events = [
        E('gev_20240514_0203', '2024/05/14 02:03:00', '02:19:00', '02:09:00', 'X1.7', 'N13E15( 3664 )', ['20240515_0000']),
        E('gev_20240514_1240', '2024/05/14 12:40:00', '13:05:00', '12:55:00', 'X1.2', 'N13E10( 3664 )', ['20240515_0000']),
    ]
    import copy
    assert merge_duplicates(copy.deepcopy(events)) == events
