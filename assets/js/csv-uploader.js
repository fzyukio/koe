import {createTable, extractHeader, convertRawUrl, showAlert, isEmpty, logError, attachEventOnce} from './utils';
import {postRequest} from './ajax-handler';
import {findColumns} from './grid-utils';
import {IsoDateValidator} from './slick-grid-addons';
const Papa = require('papaparse');


export class CsvUploader {
    init(grid, importKeys, uploadUrl) {
        const self = this;
        self.grid = grid;
        self.importKeys = importKeys;
        self.primaryKey = importKeys[0];
        self.uploadUrl = uploadUrl;
        self.extraPostArgs = {};

        const $modal = $('#upload-csv-modal');
        self.$modal = $modal;
        self.$uploadCsvBtn = $modal.find('#upload-csv-btn');
        self.$processCsvBtn = $modal.find('#process-csv-btn');

        const $uploadForm = $modal.find('#file-upload-form');
        self.$uploadInput = $uploadForm.find('input[type=file]');
        self.$modalAlertFailure = $modal.find('.alert-danger');
        self.$modalAlertWarning = $modal.find('.alert-warning');
        self.$modalAlertSuccess = $modal.find('.alert-success');

        self.$importableTableWrapper = $modal.find('#importable-table-wrapper');
        self.$unimportableTableWrapper = $modal.find('#unimportable-table-wrapper');
    }

    setExtraPostArgs(args) {
        const self = this;
        self.extraPostArgs = args;
    }

    handleImportableRows(rows, permittedCols, info, matched) {
        const self = this;
        if (info) {
            showAlert(self.$modalAlertSuccess, info, -1);
        }

        let $tableWrapper = self.$importableTableWrapper;
        let $table = $tableWrapper.find('table');
        $table.children().remove();
        createTable($table, permittedCols, rows, true);
        $tableWrapper.show();

        let gridType = self.grid.gridType;
        let missingCols = CsvUploader.findMissingCols({permittedCols, matched});

        attachEventOnce({
            element: self.$processCsvBtn,
            eventType: 'click',
            func() {
                self.uploadCsvToServer(self.uploadUrl, rows, permittedCols, missingCols, gridType).
                    then(function () {
                        self.$processCsvBtn.prop('disabled', true);
                        self.$uploadCsvBtn.prop('disabled', true);
                        self.$processCsvBtn.off('click');
                        let msg = 'Data imported successfully. Page will reload';
                        showAlert(self.$modalAlertSuccess, msg, 1500).then(function () {
                            window.location.reload();
                        });
                    }).
                    catch(function (err) {
                        showAlert(self.$modalAlertFailure, err, -1);
                    });
            },
            funcName: 'uploadCsvToServer'
        });
    }

    handleUnimportableRows(rows, permittedCols, info) {
        const self = this;
        if (info) {
            showAlert(self.$modalAlertFailure, info, -1);
        }

        let $tableWrapper = self.$unimportableTableWrapper;
        let $table = $tableWrapper.find('table');
        $table.children().remove();
        createTable($table, permittedCols, rows, true);
        $tableWrapper.show();
    }

    initUploadCsv() {
        const self = this;
        if (self.importKeys) {
            let grid = self.grid.mainGrid;

            let columns = grid.getColumns();
            let permittedCols = extractHeader(columns, 'importable', self.importKeys);
            let items = grid.getData().getItems();

            self.$uploadCsvBtn.on('click', function () {
                self.resetModal();
                self.$uploadInput.click();
            });

            self.$uploadInput.change(function (e) {
                e.preventDefault();
                let file = e.target.files[0];
                let reader = new FileReader();

                reader.onload = function () {
                    self.$uploadInput.val(null);
                    self.processCsv(reader.result, permittedCols, columns, items).
                        then(function ({allValid, rows, info, matched}) {
                            self.$processCsvBtn.prop('disabled', !allValid);

                            if (!allValid) {
                                self.handleUnimportableRows(rows, permittedCols, info);
                                return;
                            }
                            self.handleImportableRows(rows, permittedCols, info, matched);
                        }).
                        catch(function (err) {
                            logError(err);
                            self.$processCsvBtn.prop('disabled', true);
                            showAlert(self.$modalAlertFailure, err, 15000);
                        });
                };
                reader.readAsText(file);
            });

            $('#open-upload-csv-modal').click(function () {
                self.resetModal();
                self.$modal.modal('show');
            });
        }
    }

    /**
     * Remove enclosing quotes from string if exist
     * @param val
     * @returns {*}
     */
    static sanitise(val) {
        if (val.startsWith('"')) {
            val = val.substr(1, val.length - 2);
        }
        return val.trim();
    }


    /**
     * Get the field value of all item
     * @param items
     * @param columns
     */
    static getKeyFields(items, columns) {
        let retval = {};
        $.each(columns, function (_, column) {
            retval[column.field] = [];
        });

        $.each(items, function (_, item) {
            $.each(columns, function (__, column) {
                let value = item[column.field];
                if (column._formatter === 'Url') {
                    value = convertRawUrl(value).val;
                }
                retval[column.field].push(value)
            })
        });
        return retval;
    }


    /**
     * Split the list of columns from header to two array: columns allowed to import vs disallowed.
     * @param header
     * @param permittedCols names of the columns that are allowed to import.
     * @returns {{unmatched: Array, matched: {}}}
     */
    matchColumns(header, permittedCols) {
        const self = this;
        let unmatched = [];
        let matched = {};

        $.each(header, function (csvCol, column) {
            column = CsvUploader.sanitise(column);

            let permittedCol = permittedCols.indexOf(column);
            if (permittedCol > -1) {
                matched[permittedCol] = csvCol;
            }
            else {
                unmatched.push(column)
            }
        });
        if (Object.keys(matched).length === 0) {
            throw new Error('Columns in your CSV don\'t match with any importable columns');
        }

        // The key column is ALWASY the first in permittedCols and it MUST have a match in matchedCols
        // Careful, matchedCols[0] is not the first element (matchedCols is not an array), but the corresponding
        // column index of the key column in the uploaded CSV.
        let missingColumns = [];
        $.each(self.importKeys, function (ind, key) {
            if (matched[ind] !== key) {
                missingColumns.push(key);
            }
        });

        if (missingColumns.length === 0) {
            throw new Error(`The following columns: "${missingColumns}" are missing from your CSV`);
        }
        return {unmatched, matched};
    }

    /**
     * From the list of grid items and csv rows, find the rows that match grid items at key field and
     * differ from the grid data at at least one other field
     * @param items
     * @param csvRows
     * @param rowKeys
     * @param matched
     * @param permittedCols
     * @param columns SlickGrid's columns
     * @returns {{allValid: boolean, rows: *, info: *}}
     */
    getMatchedAndChangedRows(items, csvRows, rowKeys, matched, permittedCols, columns) {
        const self = this;
        let validRows = [];
        let invalidRows = [];
        let rows;
        let idMatchCount = 0;
        let totalRowCount = csvRows.length;
        let columnValidators = {};
        $.each(columns, function (index, column) {
            if (column._formatter == 'Date') {
                columnValidators[column.field] = IsoDateValidator;
            }
            else {
                columnValidators[column.field] = function () {
                    return {valid: true, msg: null};
                };
            }
            return true;
        });
        $.each(csvRows, function (_i, csvRow) {
            let rowKey = csvRow[matched[0]];
            let colVals = rowKeys[self.primaryKey];
            let rowIdx = colVals.indexOf(rowKey);
            if (rowIdx > -1) {
                idMatchCount++;
                let item = items[rowIdx];
                let itemId = item.id;
                let changed = false;
                let valid = true;
                let errors = [];

                // We skip the key column (let permittedCol = 1 instead of 0), so we add it before the loop.
                let row = [rowKey];
                for (let permittedCol = 1; permittedCol < permittedCols.length; permittedCol++) {
                    let field = permittedCols[permittedCol];
                    let csvCol = matched[permittedCol];
                    if (undefined === csvCol) {
                        row.push(null);
                        continue;
                    }

                    let csvCellVal = csvRow[csvCol];
                    let itemFieldVal = item[field];
                    let validator = columnValidators[field];

                    let validationResult = validator(csvCellVal);
                    if (validationResult.valid) {
                        if ((!isEmpty(itemFieldVal) || !isEmpty(csvCellVal)) && csvCellVal !== itemFieldVal) {
                            changed = true;
                        }
                        row.push(csvCellVal);
                    }
                    else {
                        valid = false;
                        errors.push(validationResult.msg);
                        row.push(validationResult.msg)
                    }
                }

                if (!valid) {
                    // Always put the ID last so that it will not be rendered to the table which the user can see.
                    row.push(itemId);
                    invalidRows.push(row)
                }
                // Only add rows that differ from the corresponding grid item
                else if (changed) {
                    // Always put the ID last so that it will not be rendered to the table which the user can see.
                    row.push(itemId);
                    validRows.push(row);
                }
            }
        });
        let allValid = invalidRows.length == 0;
        let info;

        if (allValid) {
            let changedCount = validRows.length;
            if (changedCount === 0) {
                throw new Error('Your CSV contains the exact same data as current on the table. The table will not be updated.');
            }
            info = `You CSV contains <strong>${totalRowCount}</strong> rows. 
                <strong>${idMatchCount}</strong> rows have matching <strong>${self.importKeys}</strong>.
                <strong>${changedCount}</strong> rows differ from table value. 
                The table will be updated based on these <strong>${changedCount}</strong> rows.`;
            rows = validRows;
        }
        else {
            info = `You CSV contains <strong>${totalRowCount}</strong> rows.
                <strong>${invalidRows.length}</strong> rows have invalid values. 
                Please fix these problem and try again.`;
            rows = invalidRows;
        }

        return {allValid, rows, info};
    }

    /**
     * Read csv from text & perform other task to arrive at {rows: the rows that will update the grid, info: information
     * about the data being imported and matched: list of columns that match the grid columns.
     * @param csvText
     * @param permittedCols
     * @param columns
     * @param items
     * @returns {Promise}
     */
    processCsv(csvText, permittedCols, columns, items) {
        const self = this;
        let importKeyColumns = findColumns(columns, self.importKeys);
        let rowKeys = CsvUploader.getKeyFields(items, importKeyColumns);

        return new Promise(function (resolve, reject) {
            try {
                let csvRows = [];
                Papa.parse(csvText, {
                    skipEmptyLines: true,
                    step(results, parser) {
                        if (results.errors.length) {
                            let errorMessage = results.errors.map((x) => x.message).join(';');
                            let e = new Error(`Error parsing CSV: ${errorMessage}`);
                            logError(e);
                            parser.abort();
                            reject(e);
                        }
                        let row = results.data[0];
                        csvRows.push(row);
                    },
                    complete() {
                        let header = csvRows.splice(0, 1)[0];
                        let {matched} = self.matchColumns(header, permittedCols);
                        let {allValid, rows, info} = self.getMatchedAndChangedRows(items, csvRows, rowKeys, matched, permittedCols, columns);
                        resolve({allValid, rows, info, matched});
                    }
                });
            }
            catch (e) {
                logError(e);
                reject(e);
            }
        });

    }


    /**
     * Upload the data to server to update grid
     * @param requestSlug
     * @param rows
     * @param attrs
     * @param missingAttrs
     * @param gridType
     * @returns {Promise}
     */
    uploadCsvToServer(requestSlug, rows, attrs, missingAttrs, gridType) {
        const self = this;
        return new Promise(function (resolve, reject) {
            let postData = {
                'grid-type': gridType,
                rows: JSON.stringify(rows),
                attrs: JSON.stringify(attrs),
                'missing-attrs': JSON.stringify(missingAttrs)
            };
            $.each(self.extraPostArgs, function (key, val) {
                postData[key] = val;
            });
            postRequest({
                requestSlug,
                data: postData,
                onSuccess(data) {
                    resolve(data);
                },
                onFailure(data) {
                    reject(new Error(data));
                }
            });
        });
    }

    /**
     * Find columns that could be imported but missing from the CSV
     * @param permittedCols
     * @param matched
     * @returns {Array}
     */
    static findMissingCols({permittedCols, matched}) {
        let missingCols = [];
        $.each(permittedCols, function (permittedColIx, permittedCol) {
            if (matched[permittedColIx] === undefined) {
                missingCols.push(permittedCol)
            }
        });

        return missingCols;
    }

    /**
     * Refresh CSV upload self.$modal before appending new data.
     */
    resetModal() {
        const self = this;
        self.$importableTableWrapper.hide();
        self.$unimportableTableWrapper.hide();

        self.$modalAlertFailure.find('.message').html('');
        self.$modalAlertSuccess.find('.message').html('');
        self.$modalAlertWarning.find('.message').html('');
        self.$modalAlertFailure.hide();
        self.$modalAlertSuccess.hide();
        self.$modalAlertWarning.hide();
        self.$processCsvBtn.prop('disabled', true);
    }
}
