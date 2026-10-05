// Shared by the chart and the CSV export, so both treat "no data" the same way.

// A catalogue has no data before its first flare or after its latest update; a bin outside that
// span is "no data", not "zero flares" (bin labels are 'YYYY', 'YYYY-MM' or 'YYYY-MM-DD')
export const covered = (data, label, bin) => {
  const first = data.coverage?.[label]
  const last = data.coverage_end?.[label]
  return (!first || bin >= first.slice(0, bin.length)) && (!last || bin <= last.slice(0, bin.length))
}

export const toCSV = (data) => {
  const labels = Object.keys(data.series)
  if (data.mode === 'counts') {
    const bins = (data.series[labels[0]] || []).map(([bin]) => bin)
    const row = (bin, i) => [bin, ...labels.map(l => covered(data, l, bin) ? data.series[l][i][1] : '')].join(',')
    return [[data.bin, ...labels].join(','), ...bins.map(row)].join('\n')
  }
  const rows = labels.flatMap(l => data.series[l].map(p => [l, p.id, p.time, p.goes_class ?? 'N/A', p.flux ?? 'N/A'].join(',')))
  return ['source,id,peak_time,goes_class,peak_flux_w_m2', ...rows].join('\n')
}
