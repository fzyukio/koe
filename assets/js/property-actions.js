import {getUrl} from './utils';

export const actionRequirements = {

    /*
     * Currently we allow deleting row only if it is new (not yet saved to the database)
     */
    'delete-property': {_isNew: true},
    'hide-property': {},
    'reorder-columns': {},
    'set-column-width': {}
};

export const interactionTypes = {
    'delete-property': 'click',
    'hide-property': 'click',
    'reorder-columns': 'reorder',
    'set-column-width': 'resize'
};


export const hasActionsOfType = function (type, actions) {
    for (let i = 0; i < actions.length; i++) {
        let action = actions[i];
        if (interactionTypes[action] === type) {
            return true;
        }
    }
    return false;
};


export const getHandlerOfActionType = function (type, actions) {
    let retval = [];
    for (let i = 0; i < actions.length; i++) {
        let action = actions[i];
        if (interactionTypes[action] === type) {
            retval.push(actionHandlers[action]);
        }
    }
    return retval;
};


export const isClickableOnRow = function (row, item, action) {
    if (interactionTypes[action] !== 'click') {
        return false;
    }
    let requirements = actionRequirements[action];
    for (let k in requirements) {
        if (Object.prototype.hasOwnProperty.call(requirements, k)) {
            let requiredValue = requirements[k];
            let actualValue = item[k];
            if (requiredValue !== actualValue) {
                return false;
            }
        }
    }
    return true;
};


const setColumnWidth = function (e, grid, gridType) {
    let colIdsWidths = {};

    /*
     * The only way to detect columns that changes width is to compare their new width with their previous ones
     */
    for (let i = 0, totI = grid.getColumns().length; i < totI; i++) {
        let column = grid.getColumns()[i];
        if (column.width !== column.previousWidth) {
            colIdsWidths[column.id] = {};
            colIdsWidths[column.id][this.action] = column.width;
        }
    }

    $.post(
        getUrl('send-request', 'set-action-values'),
        {'column-ids-action-values': JSON.stringify(colIdsWidths),
            'grid-type': gridType}
    );
};


const reorderColumn = function (e, grid, gridType) {
    let colIdToIdx = {};

    /*
     * The column's order is the same as their array index, so this is simply to send their ids and array index
     * back to the server
     */
    for (let i = 0, totI = grid.getColumns().length; i < totI; i++) {
        let column = grid.getColumns()[i];
        colIdToIdx[column.id] = {};
        colIdToIdx[column.id][this.action] = i;
    }

    $.post(
        getUrl('send-request', 'set-action-values'),
        {'column-ids-action-values': JSON.stringify(colIdToIdx),
            'grid-type': gridType}
    );
};


export const actionHandlers = {
    'set-column-width': setColumnWidth.bind({action: 'set-column-width'}),
    'reorder-columns': reorderColumn.bind({action: 'reorder-columns'})
};
