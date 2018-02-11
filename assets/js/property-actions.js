import * as utils from "utils"

export const actionIcons = {
  'delete-property': {'_default': 'fa fa-trash'},
  'hide-property': {'_default': 'fa fa-eye-slash', false: 'fa fa-eye-slash', true: 'fa fa-eye'},
};

export const actionTitles = {
  'delete-property': {'_default': 'Delete'},
  'hide-property': {'_default': 'Hide', false: 'Hide', true: 'Show'},
};

export const actionButtonStyles = {
  'delete-property': {'_default': 'btn-danger'},
  'hide-property': {'_default': 'btn-warning', false: 'btn-warning', true: 'btn-primary'},
};

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


export const hasActionsOfType = function(type, actions) {
  for (let i=0; i<actions.length; i++) {
    let action = actions[i];
    if (interactionTypes[action] === type) {
      return true;
    }
  }
  return false;
};


export const getHandlerOfActionType = function(type, actions) {
  let retval = [];
  for (let i=0; i<actions.length; i++) {
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
    if (requirements.hasOwnProperty(k)) {
      let requiredValue = requirements[k];
      let actualValue = item[k];
      if (requiredValue !== actualValue) {
        return false;
      }
    }
  }
  return true;
};

const deleteRow = function (row, grid) {
  grid.invalidateRow(row);
  grid.getData().deleteItem(row);
  grid.updateRowCount();
  grid.render();
};

/**
 * Change action value of an item when its action button is clicked on
 * @param row
 * @param grid
 */
const setActionValue = function (row, grid) {
  let items = grid.getData().getItems();
  let itemToAct = items[row];
  itemToAct._isActionValueChanged = true;
  if (itemToAct.actions === undefined){
    itemToAct.actions = {}
  }
  itemToAct.actions[this.action] = itemToAct.actions[this.action] ? !itemToAct.actions[this.action] : true;
};


const setColumnWidth = function (e, grid, gridType) {
  let colIdsWidths = {};
  let action = 'set-column-width';

  /*
   * The only way to detect columns that changes width is to compare their new width with their previous ones
   */
  for(let i = 0, totI = grid.getColumns().length; i < totI; i++){
    let column = grid.getColumns()[i];
    if (column.width !== column.previousWidth){
      colIdsWidths[column.id] = {};
      colIdsWidths[column.id][this.action] = column.width;
    }
  }

  $.post(utils.getUrl('send-data', 'change-action-values'),
    {'column-ids-action-values': JSON.stringify(colIdsWidths), 'grid-type': gridType}
  );
};


const reorderColumn = function (e, grid, gridType) {
  let colIdToIdx = {};

  /*
   * The column's order is the same as their array index, so this is simply to send their ids and array index
   * back to the server
   */
  for(let i = 0, totI = grid.getColumns().length; i < totI; i++){
    let column = grid.getColumns()[i];
    colIdToIdx[column.id] = {};
    colIdToIdx[column.id][this.action] = i;
  }

  $.post(utils.getUrl('send-data', 'change-action-values'),
    {'column-ids-action-values': JSON.stringify(colIdToIdx), 'grid-type': gridType}
  );
};


export const actionHandlers = {
  // 'delete-property': deleteRow,
  // 'hide-property': setActionValue.bind({action: 'hide-property'}),
  'set-column-width': setColumnWidth.bind({action: 'set-column-width'}),
  'reorder-columns': reorderColumn.bind({action: 'reorder-columns'})
};