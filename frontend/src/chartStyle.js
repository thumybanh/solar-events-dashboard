// One fixed look per catalogue. A source keeps its color, dash and marker when others are hidden,
// and each one differs in dash and marker as well as color, so the figure still reads in black-and-white
// print and for color-blind readers. Colors checked with the dataviz palette validator (CVD-safe);
// the green is light on white (2.7:1), which is why lines are also labeled directly.
export const SERIES = {
  LMSAL: {color: '#2a78d6', dash: null, marker: 'circle', label: 'LMSAL'},
  NOAA: {color: '#eb6834', dash: '7 4', marker: 'square', label: 'NOAA/SWPC'},
  SciQuality: {color: '#1baf7a', dash: '1 4', marker: 'triangle', label: 'NCEI SciQuality'},
}

export const SOURCE_KEYS = {LMSAL: 'lmsal', NOAA: 'noaa', SciQuality: 'sciquality'}

export const FONT = "Georgia, 'Times New Roman', Times, serif"
