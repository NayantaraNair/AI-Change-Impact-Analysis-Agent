// Test-only font response for offline `next build` verification. Production uses Google Fonts.
module.exports = {
  "https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400..700&display=swap":
    "@font-face { font-family: 'Instrument Sans'; src: local('Arial'); font-style: normal; font-weight: 400 700; }",
};
