import React from "react";
import { DropdownButton, MenuItem } from "react-bootstrap";

export class Dropdown extends React.Component {
  static getDerivedStateFromProps(nextProps) {
    return {
      headerTitle: nextProps.title.replace(
        "__replace__",
        nextProps.selectedValue
      ),
    };
  }

  constructor(props) {
    super(props);
    this.toggleItem = props.toggleItem;
    this.itemKey = props.itemKey;
    this.selectedKey = props.selectedKey;

    this.state = {
      listOpen: false,
      headerTitle: props.title,
    };
  }

  render() {
    const { list, selectedValue } = this.props;
    const { listOpen, headerTitle } = this.state;
    return (
      <DropdownButton bsStyle="default" title={headerTitle} id={this.props.id}>
        {list.map((item) => (
          <MenuItem
            className={item === selectedValue ? "active" : ""}
            key={item}
            onClick={() =>
              this.toggleItem(item, this.itemKey, this.selectedKey)
            }
          >
            {item}
          </MenuItem>
        ))}
      </DropdownButton>
    );
  }
}
