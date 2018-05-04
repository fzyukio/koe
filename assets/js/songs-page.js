import * as fg from 'flexible-grid';
import {defaultGridOptions} from './flexible-grid';
import * as ah from './audio-handler';
import {log, deepCopy, getUrl} from 'utils';
require('bootstrap-slider/dist/bootstrap-slider.js');


const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 50;


class Grid extends fg.FlexibleGrid {
    init(cls) {

        super.init({
            'grid-name': 'sequences',
            'grid-type': 'songs-grid',
            'default-field': 'filename',
            gridOptions
        });

        this.cls = cls;
    }

    /**
     * Highlight the active row on mouse over (super) and also highlight the corresponding segment on the spect
     * @param e
     * @param args
     */
    mouseHandler(e, args) {
        super.mouseHandler(e, args);

        const self = this;
        let eventType = e.type;
        let grid = args.grid;
        let dataView = grid.getData();
        let cell = grid.getCellFromEvent(e);
        if (cell) {
            let row = cell.row;
            let col = cell.cell;
            let coldef = grid.getColumns()[col];
            let rowElement = $(e.target.parentElement);
            let songId = dataView.getItem(row).id;
            self.eventNotifier.trigger(eventType, {
                e,
                songId,
                rowElement,
                coldef
            });
        }
    }
}

export const grid = new Grid();
let cls = $('#songs-grid').attr('cls');
const inputText = $('<input type="text" class="form-control"/>');
const tooltip = $('#spectrogram-details-tooltip');
const tooltipImg = tooltip.find('img');
const speedSlider = $('#speed-slider');
const gridStatus = $('#grid-status');
const gridStatusNTotal = gridStatus.find('#ntotal');

const databaseCombo = $('#database-select-combo');
const currentDatabaseAttr = databaseCombo.attr('current-attr');
const databaseClass = databaseCombo.attr('cls');

const uploadSongsBtn = $('#upload-songs-btn');
const uploadCsvBtn = $('#upload-csv-btn');
const deleteSongsBtn = $('#delete-songs-btn');

const audioUploadForm = $('#file-upload-form');
const audioUploadInput = audioUploadForm.find('input[type=file]');
const audioUploadSubmitBtn = audioUploadForm.find('input[type=submit]');

const csvUploadForm = $('#csv-upload-form');
const csvUploadInput = csvUploadForm.find('input[type=file]');
const csvUploadSubmitBtn = csvUploadForm.find('input[type=submit]');

let ce;

const initSlider = function () {
    speedSlider.slider();

    speedSlider.on('slide', function (slideEvt) {
        ah.changePlaybackSpeed(slideEvt.value);
    });

    $('.slider').on('click', function () {
        let newvalue = $('.tooltip-inner').text();
        ah.changePlaybackSpeed(parseInt(newvalue));
    });
};

const playAudio = function (e, args) {
    let cellElement = $(args.e.target);
    let hasSyllable = cellElement.closest('.syllable');
    if (hasSyllable.length == 1) {
        let audioUrl = hasSyllable.parent().find('.full-audio').attr('song-url');
        let start = parseInt(hasSyllable.attr('start')) / 1000.0;
        let end = parseInt(hasSyllable.attr('end')) / 1000.0;

        let args_ = {
            url: audioUrl,
            startSecond: start,
            endSecond: end
        };
        ah.playAudioFromUrl(args_);
    }
};

/**
 * Triggered on click. If the cell is not editable and is of type text, integer, float, highlight the entire cell
 * for Ctrl + C
 *
 * @param e
 * @param args
 */
const selectTextForCopy = function (e, args) {
    let coldef = args.coldef;
    let editable = coldef.editable;
    let copyable = coldef.copyable;

    if (!editable && copyable) {
        let cellElement = $(args.e.target);
        cellElement.selectText();
    }
};

/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    log('subscribeFlexibleEvents called from songs-pages');
    grid.on('click', function (...args) {
        let e = args[0];
        e.preventDefault();
        playAudio(...args);
        selectTextForCopy(...args);
        clearSpectrogram(...args);
        showBigSpectrogram(...args);
    });

    /**
     * When songs are selected, enable delete button
     */
    function enableDeleteSongsBtn() {
        deleteSongsBtn.prop('disabled', false);
    }

    /**
     * When songs are removed, if there is songs left, disable the delete button
     * @param e event
     * @param args contains 'grid' - the main SlickGrid
     */
    function disableDeleteSongsBtn(e, args) {
        let grid_ = args.grid;
        if (grid_.getSelectedRows().length == 0) deleteSongsBtn.prop('disabled', true);
    }

    grid.on('row-added', enableDeleteSongsBtn);
    grid.on('rows-added', enableDeleteSongsBtn);

    grid.on('row-removed', disableDeleteSongsBtn);
    grid.on('rows-removed', disableDeleteSongsBtn);
};


/**
 * Subscribe to events on the slick grid. This must be called everytime the slick is reconstructed, e.g. when changing
 * screen orientation or size
 */
const subscribeSlickEvents = function () {

    grid.subscribeDv('onRowCountChanged', function (e, args) {
        let currentRowCount = args.current;
        gridStatusNTotal.html(currentRowCount);
    });

    grid.on('mouseleave', clearSpectrogram);
};


/**
 * Redraw the table on orientation changed
 */
export const orientationChange = function () {
    grid.redrawMainGrid({
        rowMoveable: true,
        multiSelect: true
    }, function () {
        subscribeSlickEvents();
    });
};


const showBigSpectrogram = function (e, args) {
    e.preventDefault();
    let cellElement = $(args.e.target);
    let isSyllable = cellElement.closest('.syllable');
    if (isSyllable.length == 1) {
        const imgSrc = isSyllable.attr('imgsrc');
        if (imgSrc) {
            tooltipImg.attr('src', imgSrc);
            tooltip.removeClass('hidden');

            const panelHeight = $('#songs-grid').height();
            const imgWidth = tooltipImg.width();
            const imgHeight = tooltipImg.height();

            const pos = isSyllable.offset();
            const cellTop = pos.top;
            const cellLeft = pos.left;

            let cellBottom = cellTop + isSyllable.height();
            let cellCentreX = cellLeft + (isSyllable.width() / 2);
            let imgLeft = cellCentreX - (imgWidth / 2);

            let left, top;

            if (cellBottom < panelHeight / 2) {
                top = cellBottom + 20 + 'px';
            }
            else {
                top = cellTop - 40 - imgHeight + 'px';
            }

            if (imgLeft > 0) {
                left = imgLeft + 'px';
            }
            else {
                left = '';
            }
            tooltip.css('left', left).css('top', top);
        }
    }
};


/**
 * Hide the tooltip and remove highlight from the active image
 */
const clearSpectrogram = function () {
    tooltip.addClass('hidden');
};


/**
 * Set the focus on the grid right after page is loaded.
 * This is mainly so that user can use Page Up and Page Down right away
 */
const focusOnGridOnInit = function () {
    $($('div[hidefocus]')[0]).focus();
};


/**
 * When user clicks on the "create new database" button from the drop down menu, show a dialog
 * asking for name. Send the name to the server to check for duplicate. If there exists a database with the same name,
 * repeat this process. Only dismiss the dialog if a new database is created.
 * @param errorMessage to be shown if not undefined
 */
const showCreateDatabaseDialog = function (errorMessage) {
    ce.dialogModalTitle.html('Creating a new database...');
    ce.dialogModalBody.html('<label>Give it a name</label>');
    ce.dialogModalBody.append(inputText);
    if (errorMessage) {
        ce.dialogModalBody.append(`<p>${errorMessage}</p>`);
    }

    ce.dialogModal.modal('show');

    ce.dialogModalOkBtn.one('click', function () {
        ce.dialogModal.modal('hide');
        let url = getUrl('send-request', 'koe/create-database');
        let value = inputText.val();
        inputText.val('');

        $.post(url, {name: value}, function (err) {
            ce.dialogModal.modal('hide');
            ce.dialogModal.one('hidden.bs.modal', function () {
                if (err) {
                    showCreateDatabaseDialog(err);
                }
                else {
                    location.reload();
                }
            });
        });
    });
};


/**
 * Allow user to upload songs
 */
const initUploadSongsBtn = function () {

    uploadSongsBtn.click(function () {
        audioUploadInput.click();
    });

    uploadCsvBtn.click(function () {
        csvUploadInput.click();
    });

    audioUploadInput.change(function () {
        audioUploadSubmitBtn.click();
    });

    csvUploadInput.change(function () {
        csvUploadSubmitBtn.click();
    });

    const responseHandler = function (response) {
        let message = 'Files successfully imported. Page will reload shortly.';
        let alertEl = ce.alertSuccess;
        if (response != 'ok') {
            message = `Something's wrong. The server says "${response}". Version not imported.
                       But good news is your current data is still intact.`;
            alertEl = ce.alertFailure;
        }
        alertEl.html(message);
        alertEl.fadeIn().delay(4000).fadeOut(400, function () {
            location.reload();
        });
    };

    audioUploadForm.submit(function (e) {
        e.preventDefault();
        let formData = new FormData(this);
        $.ajax({
            url: getUrl('send-request', 'koe/import-audio-files'),
            type: 'POST',
            data: formData,
            success: responseHandler,
            // !IMPORTANT: this tells jquery to not set expectation of the content type.
            // If not set to false it will not send the file
            contentType: false,

            // !IMPORTANT: this tells jquery to not convert the form data into string.
            // If not set to false it will raise "IllegalInvocation" exception
            processData: false
        });
    });

    csvUploadForm.submit(function (e) {
        e.preventDefault();
        let formData = new FormData(this);
        $.ajax({
            url: getUrl('send-request', 'koe/import-audio-metadata'),
            type: 'POST',
            data: formData,
            success: responseHandler,
            // !IMPORTANT: this tells jquery to not set expectation of the content type.
            // If not set to false it will not send the file
            contentType: false,

            // !IMPORTANT: this tells jquery to not convert the form data into string.
            // If not set to false it will raise "IllegalInvocation" exception
            processData: false
        });
    });
};

/**
 * Allows user to remove songs
 */
const initDeleteSongsBtn = function () {
    deleteSongsBtn.click(function () {
        let url = getUrl('send-request', 'koe/delete-songs');
        let grid_ = grid.mainGrid;
        let selectedRows = grid_.getSelectedRows();
        let numRows = selectedRows.length;
        let ids = [];
        let selectedItems = [];
        let dataView = grid_.getData();
        for (let i = 0; i < numRows; i++) {
            let item = dataView.getItem(selectedRows[i]);
            ids.push(item.id);
            selectedItems.push(item);
        }

        let databaseId = databaseCombo.attr('database');

        ce.dialogModalTitle.html(`Confirm delete ${numRows} song(s)`);
        ce.dialogModalBody.html(`Are you sure you want to delete these songs and all data associated with it? 
        Audio files (all formats) are also deleted. This action is not reverseable.`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.one('click', function () {
            ce.dialogModal.modal('hide');
            $.post(
                url, {ids: JSON.stringify(ids),
                    database: databaseId},
                function (response) {
                    let message = 'Files successfully deleted. This page will reload';
                    let alertEl = ce.alertSuccess;
                    let callback = function () {
                        location.reload();
                    };
                    if (response != 'ok') {
                        message = `Something's wrong. The server says ${response}. Files might have been deleted.`;
                        alertEl = ce.alertFailure;
                        callback = undefined;
                    }
                    alertEl.html(message);
                    alertEl.fadeIn().delay(4000).fadeOut(400, callback);
                }
            );
        })
    });
};


export const run = function (commonElements) {
    ce = commonElements;
    ah.initAudioContext();

    grid.init(cls);
    grid.initMainGridHeader({multiSelect: true}, function () {
        grid.initMainGridContent({'__extra__cls': cls}, focusOnGridOnInit);
        subscribeSlickEvents();
        subscribeFlexibleEvents();
    });

    $('.select-database').on('click', function (e) {
        e.preventDefault();

        let parent = $(this).parent();
        if (parent.hasClass('not-active')) {
            let databaseId = this.getAttribute('database');

            $.post(
                getUrl('send-request', 'change-extra-attr-value'),
                {
                    'attr': currentDatabaseAttr,
                    'klass': databaseClass,
                    'value': databaseId
                },
                function () {
                    grid.initMainGridContent({'__extra__cls': cls}, focusOnGridOnInit);
                }
            );

            /* Update the button */
            databaseCombo.attr('database', databaseId);
            $('.database-value').val(databaseId);
            parent.parent().find('li.active').removeClass('active').addClass('not-active');
            parent.removeClass('not-active').addClass('active');
        }
    });

    $('#create-database-btn').on('click', function (e) {
        e.preventDefault();
        showCreateDatabaseDialog();
    });

    initSlider();
};

export const postRun = function () {
    subscribeFlexibleEvents();
    initUploadSongsBtn();
    initDeleteSongsBtn();
};
