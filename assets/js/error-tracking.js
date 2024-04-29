/* global Raven */
export const showErrorDialog = function (eventId) {
  Raven.showReportDialog({
    eventId,
    dsn: "https://657ede38a2d94950bf0bf1d7c6907945@sentry.io/1212536",
  });
};

window.showErrorDialog = showErrorDialog;
