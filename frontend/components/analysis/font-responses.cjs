// Build-only fixture for environments without access to fonts.googleapis.com.
// Enable explicitly with NEXT_FONT_GOOGLE_MOCKED_RESPONSES; production is unchanged.
const css = "@font-face { font-family: 'Instrument Sans'; src: local('Arial'); font-style: normal; font-weight: 400 700; }";
module.exports = {
  "https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400..700&display=swap": css,
};
