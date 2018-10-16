import {postRequest} from './ajax-handler';
import {queryAndPlayAudio, initAudioContext} from './audio-handler';


const trackInfoForm = $('#contact-us-form');
const saveTrackInfoBtn = trackInfoForm.find('#submit-inquiry');


const initSaveTrackInfoBtn = function () {
    saveTrackInfoBtn.click(function () {
        trackInfoForm.submit();
    });

    trackInfoForm.submit(function (e) {
        e.preventDefault();
        let formData = new FormData(this);
        let url = this.getAttribute('url');

        postRequest({
            url,
            data: formData,
            onSuccess (response) {
                let formHtml = response.html;

                if (formHtml) {
                    trackInfoForm.find('.replaceable').html(formHtml);
                }

                if (response.success) {
                    saveTrackInfoBtn.remove();
                }
            }
        });
        return false;
    });
};


export const run = function () {
    initSaveTrackInfoBtn();
    initAudioContext();
    $('#koe-logo .playable').click(function () {
        let audioSrc = this.getAttribute('audio-src');
        queryAndPlayAudio({
            url: audioSrc,
            cacheKey: audioSrc
        })
    });
    return Promise.resolve();
};
