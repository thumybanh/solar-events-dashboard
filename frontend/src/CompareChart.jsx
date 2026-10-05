import { forwardRef, useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { SERIES, FONT } from './chartStyle.js'
import { covered as inCoverage } from './compareData.js'

// drawn in a fixed coordinate space and scaled by the browser, so the exported SVG matches the screen
const WIDTH = 920
const HEIGHT = 470
const MARGIN = {top: 40, right: 112, bottom: 52, left: 70}
const INK = '#111'
const GRID = '#ebebeb'
const MAX_MARKED_BINS = 60 // beyond this, markers turn a line into a smear

const CLASS_BANDS = [['A', 1e-8], ['B', 1e-7], ['C', 1e-6], ['M', 1e-5], ['X', 1e-4]]
const SUPERSCRIPT = {'-': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹'}
const powerOfTen = (v) => `10${String(Math.round(Math.log10(v))).replace(/./g, ch => SUPERSCRIPT[ch])}`

const parseBin = (label) => {
  const [y, m = '01', d = '01'] = label.split('-')
  return new Date(Date.UTC(+y, +m - 1, +d))
}
const parseTime = (text) => new Date(text.replace(' ', 'T') + 'Z')

const BIN_WORD = {day: 'day', month: 'month', year: 'year'}
const binFormat = {day: d3.utcFormat('%Y-%m-%d'), month: d3.utcFormat('%Y-%m'), year: d3.utcFormat('%Y')}

// paper-style axis: thin black line, ticks pointing into the plot, serif labels
const styleAxis = (g) => {
  g.selectAll('path, line').attr('stroke', INK).attr('stroke-width', 0.8)
  g.selectAll('text').attr('fill', INK).attr('font-family', FONT).attr('font-size', 12)
}

const marker = (selection, shape, size) => {
  if (shape === 'circle') return selection.append('circle').attr('r', size)
  if (shape === 'square') return selection.append('rect').attr('x', -size * 0.88).attr('y', -size * 0.88).attr('width', size * 1.76).attr('height', size * 1.76)
  const s = size * 1.25
  return selection.append('path').attr('d', `M0,${-s}L${s * 0.95},${s * 0.65}L${-s * 0.95},${s * 0.65}Z`)
}

function drawLegend(svg, labels, open = false){
  const box = svg.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top - 17})`)
  labels.forEach((label, i) => {
    const style = SERIES[label]
    const row = box.append('g').attr('transform', `translate(${i * 170},0)`)
    row.append('line').attr('x1', 0).attr('x2', 30).attr('stroke', style.color).attr('stroke-width', 1.8)
      .attr('stroke-dasharray', style.dash).attr('stroke-linecap', 'round')
    const m = marker(row.append('g').attr('transform', 'translate(15,0)'), style.marker, 3.6)
    if (open) m.attr('fill', '#fff').attr('stroke', style.color).attr('stroke-width', 1.4)
    else m.attr('fill', style.color)
    row.append('text').attr('x', 38).attr('dy', '0.35em').text(style.label)
      .attr('font-family', FONT).attr('font-size', 12).attr('fill', INK)
  })
}

function drawCounts(svg, data, tooltip){
  const labels = Object.keys(data.series)
  const bins = (data.series[labels[0]] || []).map(([bin]) => bin)
  if (!bins.length) return
  const dates = bins.map(parseBin)
  const plotW = WIDTH - MARGIN.left - MARGIN.right
  const plotH = HEIGHT - MARGIN.top - MARGIN.bottom
  const maxCount = d3.max(labels, l => d3.max(data.series[l], ([, n]) => n)) || 1

  const x = d3.scaleUtc().domain(d3.extent(dates)).range([0, plotW])
  if (dates.length === 1) x.domain([dates[0], d3.utcDay.offset(dates[0], 1)])
  const y = d3.scaleLinear().domain([0, maxCount * 1.08]).nice().range([plotH, 0])
  const plot = svg.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top})`)

  plot.append('g').selectAll('line').data(y.ticks(6)).join('line')
    .attr('x1', 0).attr('x2', plotW).attr('y1', y).attr('y2', y).attr('stroke', GRID).attr('stroke-width', 0.8)

  const xTicks = data.bin === 'year' ? d3.utcYear.every(Math.max(1, Math.ceil(bins.length / 12)))
    : data.bin === 'month' ? Math.min(10, bins.length) : Math.min(10, bins.length)
  plot.append('g').attr('transform', `translate(0,${plotH})`)
    .call(d3.axisBottom(x).ticks(xTicks).tickFormat(data.bin === 'day' ? null : binFormat[data.bin]).tickSizeInner(-5).tickSizeOuter(0).tickPadding(7))
    .call(styleAxis)
  plot.append('g').call(d3.axisLeft(y).ticks(6, ',d').tickSizeInner(-5).tickSizeOuter(0).tickPadding(7)).call(styleAxis)
  plot.append('rect').attr('width', plotW).attr('height', plotH).attr('fill', 'none').attr('stroke', INK).attr('stroke-width', 0.8)

  const covered = (label, bin) => inCoverage(data, label, bin)
  const ends = []
  labels.forEach(label => {
    const style = SERIES[label]
    const values = data.series[label]
    const line = d3.line().defined(([bin]) => covered(label, bin)).x((_, i) => x(dates[i])).y(([, n]) => y(n))
    plot.append('path').datum(values).attr('d', line).attr('fill', 'none').attr('stroke', style.color)
      .attr('stroke-width', 1.7).attr('stroke-dasharray', style.dash).attr('stroke-linecap', 'round').attr('stroke-linejoin', 'round')
    if (values.length <= MAX_MARKED_BINS) {
      values.forEach(([bin, n], i) => {
        if (!covered(label, bin)) return
        marker(plot.append('g').attr('transform', `translate(${x(dates[i])},${y(n)})`), style.marker, 3.4)
          .attr('fill', style.color).attr('stroke', '#fff').attr('stroke-width', 1)
      })
    }
    const last = values.filter(([bin]) => covered(label, bin)).pop()
    if (last) ends.push({label, y: y(last[1])})
  })

  // direct labels at the right end of each line, nudged apart so they never overlap
  ends.sort((a, b) => a.y - b.y)
  for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 14)
  ends.forEach(({label, y: ly}) => {
    plot.append('text').attr('x', plotW + 8).attr('y', ly).attr('dy', '0.35em').text(SERIES[label].label)
      .attr('font-family', FONT).attr('font-size', 12).attr('fill', INK)
  })

  svg.append('text').attr('transform', `translate(18,${MARGIN.top + plotH / 2}) rotate(-90)`).attr('text-anchor', 'middle')
    .text(`Flares per ${BIN_WORD[data.bin]}`).attr('font-family', FONT).attr('font-size', 13).attr('fill', INK)
  svg.append('text').attr('x', MARGIN.left + plotW / 2).attr('y', HEIGHT - 10).attr('text-anchor', 'middle')
    .text(data.bin === 'year' ? 'Year' : 'Date (UTC)').attr('font-family', FONT).attr('font-size', 13).attr('fill', INK)
  drawLegend(svg, labels)

  // hover: a crosshair on the nearest bin and every source's count for it
  const cross = plot.append('line').attr('y1', 0).attr('y2', plotH).attr('stroke', '#888').attr('stroke-width', 0.8).attr('visibility', 'hidden')
  plot.append('rect').attr('width', plotW).attr('height', plotH).attr('fill', 'transparent')
    .on('mousemove', (event) => {
      const [mx] = d3.pointer(event)
      const i = d3.minIndex(dates, d => Math.abs(x(d) - mx))
      cross.attr('x1', x(dates[i])).attr('x2', x(dates[i])).attr('visibility', 'visible')
      tooltip.show(event, `<strong>${bins[i]}</strong>` + labels.map(l =>
        `<div><span class="swatch" style="border-top:2px ${!SERIES[l].dash ? 'solid' : SERIES[l].dash.startsWith('1 ') ? 'dotted' : 'dashed'} ${SERIES[l].color}"></span>${SERIES[l].label}: ${covered(l, bins[i]) ? data.series[l][i][1].toLocaleString() : 'no data'}</div>`).join(''))
    })
    .on('mouseleave', () => { cross.attr('visibility', 'hidden'); tooltip.hide() })
}

function drawFlares(svg, data, tooltip){
  const labels = Object.keys(data.series)
  const points = labels.flatMap(label => data.series[label].filter(p => p.flux > 0).map(p => ({...p, label, date: parseTime(p.time)})))
  const plotW = WIDTH - MARGIN.left - MARGIN.right
  const plotH = HEIGHT - MARGIN.top - MARGIN.bottom
  const start = parseBin(data.start)
  const end = d3.utcDay.offset(parseBin(data.end), 1)
  const lo = Math.min(1e-7, d3.min(points, p => p.flux) || 1e-7)
  const hi = Math.max(1e-4, d3.max(points, p => p.flux) || 1e-4)

  const x = d3.scaleUtc().domain([start, end]).range([0, plotW])
  const y = d3.scaleLog().domain([10 ** Math.floor(Math.log10(lo)), 10 ** Math.ceil(Math.log10(hi))]).range([plotH, 0])
  const decades = d3.range(Math.round(Math.log10(y.domain()[0])), Math.round(Math.log10(y.domain()[1])) + 1).map(e => 10 ** e)
  const plot = svg.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top})`)

  plot.append('g').selectAll('line').data(decades).join('line')
    .attr('x1', 0).attr('x2', plotW).attr('y1', y).attr('y2', y).attr('stroke', GRID).attr('stroke-width', 0.8)
  plot.append('g').attr('transform', `translate(0,${plotH})`)
    .call(d3.axisBottom(x).ticks(8).tickSizeInner(-5).tickSizeOuter(0).tickPadding(7)).call(styleAxis)
  plot.append('g').call(d3.axisLeft(y).tickValues(decades).tickFormat(powerOfTen).tickSizeInner(-5).tickSizeOuter(0).tickPadding(7)).call(styleAxis)
  plot.append('rect').attr('width', plotW).attr('height', plotH).attr('fill', 'none').attr('stroke', INK).attr('stroke-width', 0.8)

  // GOES class letters on the right edge, centered in their decade
  CLASS_BANDS.filter(([, base]) => base >= y.domain()[0] && base < y.domain()[1]).forEach(([letter, base]) => {
    plot.append('text').attr('x', plotW + 10).attr('y', y(base * Math.sqrt(10))).attr('dy', '0.35em').text(letter)
      .attr('font-family', FONT).attr('font-size', 13).attr('font-weight', 'bold').attr('fill', INK)
  })
  svg.append('text').attr('x', WIDTH - MARGIN.right + 30).attr('y', MARGIN.top + plotH / 2).attr('text-anchor', 'middle')
    .attr('transform', `rotate(90 ${WIDTH - MARGIN.right + 30} ${MARGIN.top + plotH / 2})`)
    .text('GOES class').attr('font-family', FONT).attr('font-size', 13).attr('fill', INK)

  labels.forEach(label => {
    const style = SERIES[label]
    points.filter(p => p.label === label).forEach(p => {
      // open marks: where the catalogues report the same flare, every catalogue's mark stays visible
      marker(plot.append('g').attr('transform', `translate(${x(p.date)},${y(p.flux)})`), style.marker, 3.8)
        .attr('fill', 'none').attr('stroke', style.color).attr('stroke-width', 1.3)
    })
  })

  svg.append('text').attr('transform', `translate(18,${MARGIN.top + plotH / 2}) rotate(-90)`).attr('text-anchor', 'middle')
    .text('Peak flux, 1–8 Å (W m⁻²)').attr('font-family', FONT).attr('font-size', 13).attr('fill', INK)
  svg.append('text').attr('x', MARGIN.left + plotW / 2).attr('y', HEIGHT - 10).attr('text-anchor', 'middle')
    .text('Peak time (UTC)').attr('font-family', FONT).attr('font-size', 13).attr('fill', INK)
  drawLegend(svg, labels, true)

  // hover: the nearest flare within 12 px
  const finder = d3.Delaunay.from(points, p => x(p.date), p => y(p.flux))
  const ring = plot.append('circle').attr('r', 7).attr('fill', 'none').attr('stroke', INK).attr('stroke-width', 1).attr('visibility', 'hidden')
  plot.append('rect').attr('width', plotW).attr('height', plotH).attr('fill', 'transparent')
    .on('mousemove', (event) => {
      const [mx, my] = d3.pointer(event)
      const i = points.length ? finder.find(mx, my) : -1
      const p = points[i]
      if (!p || Math.hypot(x(p.date) - mx, y(p.flux) - my) > 12) { ring.attr('visibility', 'hidden'); tooltip.hide(); return }
      ring.attr('cx', x(p.date)).attr('cy', y(p.flux)).attr('visibility', 'visible')
      tooltip.show(event, `<strong>${SERIES[p.label].label}</strong><div>${p.id}</div><div>Peak ${p.time} UTC</div>` +
        `<div>Class ${p.goes_class ?? 'N/A'} · ${p.flux.toExponential(2)} W m⁻²</div>`)
    })
    .on('mouseleave', () => { ring.attr('visibility', 'hidden'); tooltip.hide() })
}

const CompareChart = forwardRef(function CompareChart({data}, svgRef){
  const tipRef = useRef(null)

  useEffect(() => {
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    svg.append('rect').attr('width', WIDTH).attr('height', HEIGHT).attr('fill', '#fff')
    const wrap = svgRef.current.parentNode
    const tooltip = {
      show: (event, html) => {
        const [px, py] = d3.pointer(event, wrap)
        const tip = tipRef.current
        tip.innerHTML = html
        tip.style.visibility = 'visible'
        // keep the box inside the chart: flip to the left of the cursor near the right edge
        const left = px + 14 + tip.offsetWidth > wrap.clientWidth ? px - 14 - tip.offsetWidth : px + 14
        tip.style.left = `${left}px`
        tip.style.top = `${Math.max(0, py - tip.offsetHeight - 8)}px`
      },
      hide: () => { tipRef.current.style.visibility = 'hidden' },
    }
    if (data.mode === 'flares') drawFlares(svg, data, tooltip)
    else drawCounts(svg, data, tooltip)
  }, [data, svgRef])

  return (
    <div className="chart-wrap">
      <svg ref={svgRef} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} xmlns="http://www.w3.org/2000/svg" role="img"
        aria-label="Comparison of flare catalogues" />
      <div ref={tipRef} className="chart-tooltip" style={{visibility: 'hidden'}} />
    </div>
  )
})

export default CompareChart
