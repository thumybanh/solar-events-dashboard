from noaa_matcher import match


def L(id, start, cls, stop='23:59:00'):
    return {'event_id': id, 'event_start': f'2024/05/14 {start}', 'event_peak': start, 'event_stop': stop,
            'event_GOES': cls}


def N(id, begin, cls, end=None):
    return {'event_id': id, 'date': '2024-05-14', 'begin': begin and f'2024-05-14 {begin}',
            'end': end and f'2024-05-14 {end}', 'goes_class': cls}


def test_high_low_na_both_directions():
    lm = [L('a', '10:00:00', 'M1.0'), L('b', '11:00:00', 'M1.0'), L('c', '12:00:00', 'M1.0')]
    no = [N('x', '10:02:00', 'M1.0'), N('y', '11:01:00', 'M1.1'), N('z', '13:00:00', 'C1.0')]
    match(lm, no)
    assert [e['quality_flag'] for e in lm] == ['HIGH', 'LOW', 'N/A']
    assert [e['quality_flag'] for e in no] == ['HIGH', 'LOW', 'N/A']
    assert lm[0]['matched_noaa_id'] == 'x' and no[0]['matched_lmsal_id'] == 'a'
    assert lm[1]['matched_noaa_id'] is None and no[1]['matched_lmsal_id'] is None


def test_closest_same_class_wins():
    lm = [L('a', '10:00:00', 'M1.0')]
    no = [N('far', '10:03:00', 'M1.0'), N('near', '10:01:00', 'M1.0')]
    match(lm, no)
    assert lm[0]['matched_noaa_id'] == 'near'


def test_missing_begin_or_class_is_na():
    lm = [L('a', '10:00:00', 'M1.0')]
    no = [N('nob', None, 'M1.0'), N('noc', '10:00:00', None)]
    match(lm, no)
    assert [e['quality_flag'] for e in no] == ['N/A', 'N/A']
    assert lm[0]['quality_flag'] == 'LOW'  # 'noc' starts within 3 min, but its class can't agree


def test_end_time_diff_only_for_high():
    lm = [L('a', '10:00:00', 'M1.0', stop='10:20:00'), L('b', '11:00:00', 'M1.0', stop='11:20:00')]
    no = [N('x', '10:01:00', 'M1.0', end='10:30:00'), N('y', '11:01:00', 'C1.0', end='11:30:00')]
    match(lm, no)
    assert lm[0]['end_time_diff'] == -10
    assert lm[1]['end_time_diff'] is None


def merged(kept, *others):
    kept['merged_from'] = [{'event_id': o['event_id'], 'event_start': o['event_start'], 'event_stop': o['event_stop']} for o in others]
    return kept


def test_merged_flare_matches_noaa_through_any_of_its_start_times():
    # kept version starts 07:50, but LMSAL also listed it at 06:17, which NOAA has
    lm = [merged(L('gev_0750', '07:50:00', 'C1.2', stop='08:10:00'), L('gev_0617', '06:17:00', 'C1.2', stop='06:40:00'))]
    no = [N('n6050', '06:17:00', 'C1.2', end='06:30:00')]
    match(lm, no)
    assert lm[0]['quality_flag'] == 'HIGH' and lm[0]['matched_noaa_id'] == 'n6050'
    assert lm[0]['matched_via'] == 'gev_0617'
    assert lm[0]['end_time_diff'] == 10          # measured with the version that matched (06:40 vs 06:30)
    assert no[0]['quality_flag'] == 'HIGH' and no[0]['matched_lmsal_id'] == 'gev_0750'


def test_own_start_is_preferred_when_it_matches_as_well():
    lm = [merged(L('gev_a', '10:00:00', 'M1.0'), L('gev_b', '10:01:00', 'M1.0'))]
    no = [N('x', '10:01:00', 'M1.0')]
    match(lm, no)
    assert lm[0]['matched_via'] == 'gev_b'  # b is closer (0 min) than the kept start (1 min)
    lm = [merged(L('gev_a', '10:01:00', 'M1.0'), L('gev_b', '10:00:00', 'M1.0'))]
    match(lm, no)
    assert lm[0]['matched_via'] == 'gev_a'


def test_unmatched_merged_flare_is_na_and_has_no_matched_via():
    lm = [merged(L('gev_a', '10:00:00', 'M1.0'), L('gev_b', '10:20:00', 'M1.0'))]
    match(lm, [N('x', '12:00:00', 'M1.0')])
    assert (lm[0]['quality_flag'], lm[0]['matched_via']) == ('N/A', None)
