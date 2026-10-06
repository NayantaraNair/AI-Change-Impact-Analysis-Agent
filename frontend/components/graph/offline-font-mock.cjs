// Verification only: Next's official font-fetch test hook keeps offline builds off the network.
// Do not set NEXT_FONT_GOOGLE_MOCKED_RESPONSES for a production build or screenshot review.
module.exports = {
  "https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400..700&display=swap":
    "@font-face { font-family: 'Instrument Sans'; font-style: normal; font-weight: 400 700; src: local('Arial'); }",
};
