module.exports = {
  content: ['./**/templates/**/*.html', './**/static/**/*.js'],
  theme: { extend: {
    colors: { paper:'#F7F4EC', forest:'#1E3D32', 'forest-deep':'#14291F', gold:'#E8C56A', ink:'#2B3A67', 'ink-soft':'#6B7594', present:'#4C7A5D', absent:'#B33A3A' },
    fontFamily: { display:['Hind Siliguri','sans-serif'], sans:['Hind Siliguri','sans-serif'] }
  }},
  safelist: [{ pattern: /(bg|text|border|ring|from|via|to)-(red|green|yellow|blue|indigo|purple|pink|orange|emerald|teal|cyan|gray|slate)-(50|100|200|300|400|500|600|700|800|900)/ }],
  plugins: []
};
