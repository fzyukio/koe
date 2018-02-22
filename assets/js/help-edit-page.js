let submitBtn = $('#submit-content-btn');
let form = $('#help-content-wrapper form');

/**
 * As the submit button is not part of the form, init the click behaviour
 */
export const run = function () {
    submitBtn.click(function () {
        form.submit();
    })
};