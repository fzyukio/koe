import { Dropdown } from "./Dropdown";

require("bootstrap-slider/dist/bootstrap-slider.js");

import React from "react";
import { getUrl, deepCopy, isNull } from "../utils";
import ReactDOM from "react-dom";
import {
  Modal,
  Form,
  Col,
  FormControl,
  FormGroup,
  ButtonToolbar,
  DropdownButton,
  MenuItem,
  MenuItemLink,
} from "react-bootstrap";

import $ from "jquery";

class SpectrogramControlForm extends React.Component {
  toggleSelected(selectedItem, itemKey, selectedKey) {
    let list = this.constant[itemKey];
    let selected;

    $.each(list, function (idx, item) {
      if (item === selectedItem) {
        selected = item;
        return false;
      }
    });
    let state = {};
    state[selectedKey] = selected;
    this.setState(state);
  }

  handleFieldChange(event) {
    let element = event.target;
    let elementId = element.getAttribute("id");
    let value = element.value;
    let state = {};
    state[elementId] = value;
    this.setState(state);
  }

  constructor(props) {
    super(props);
    this.handleSubmit = this.handleSubmit.bind(this);
    this.toggleSelected = this.toggleSelected.bind(this);
    this.handleFieldChange = this.handleFieldChange.bind(this);
    this.handleSuccess = props.onSuccess;
    this.handleFailure = props.onFailure;
    this.nChannels = props.nChannels;
    this.spectViz = props.spectViz;

    this.constant = {
      zooms: [25, 50, 100, 200, 300, 400, 500, 600, 700, 800],
      colourMaps: ["Green", "Jet", "Gray"],
      channels: [],
    };

    for (let i = 0; i < this.nChannels; i++) {
      this.constant["channels"].push(i + 1);
    }

    this.state = {
      zoom: props.zoom,
      colourMap: props.colourMap,
      channel: 1,
    };

    this.originalState = deepCopy(this.state);
  }

  handleSubmit(e) {
    e.preventDefault();
    let self = this;
    let state = this.state;

    this.spectViz.resetArgs({
      colourMap: state["colourMap"],
      zoom: state["zoom"],
    });

    this.spectViz.setChannel(state["channel"] - 1);
    this.spectViz.initCanvas();
    this.spectViz.visualisationPromiseChainHead.cancel();
    this.spectViz.visualisationPromiseChainHead = undefined;
    this.spectViz.imagesAreInitialised = false;
    this.spectViz.visualiseSpectrogram();
    this.spectViz.drawBrush();
    this.spectViz.displaySegs();

    let fileId = this.spectViz.audioData.fileId;

    if (!isNull(fileId)) {
      let url = getUrl(
        "send-request",
        "koe/save-database-spectrogram-preference"
      );
      let data = {
        "file-id": this.spectViz.audioData.fileId,
        colourmap: state["colourMap"],
        zoom: state["zoom"],
      };

      $.post(url, data)
        .done(function (response) {
          response = JSON.parse(response);
          console.log(response);
          self.handleSuccess();
        })
        .fail(function (response) {
          let errorMessage = JSON.parse(response.responseText);
          self.handleFailure(errorMessage);
        });
    }
  }

  render() {
    return (
      <Form horizontal onSubmit={this.handleSubmit} id="spectrogramControlForm">
        <FormGroup>
          <Col sm={4}>Channel</Col>
          <Col sm={8}>
            <Dropdown
              id="channel-select"
              title="__replace__"
              list={this.constant.channels}
              itemKey="channels"
              selectedKey="channel"
              selectedValue={this.state["channel"]}
              toggleItem={this.toggleSelected}
            />
          </Col>
        </FormGroup>

        <FormGroup>
          <Col sm={4}>Colour Map</Col>
          <Col sm={8}>
            <Dropdown
              id="colourMap-select"
              title="__replace__"
              list={this.constant.colourMaps}
              itemKey="colourMaps"
              selectedKey="colourMap"
              selectedValue={this.state["colourMap"]}
              toggleItem={this.toggleSelected}
            />
          </Col>
        </FormGroup>

        <FormGroup>
          <Col sm={4}>Zoom</Col>
          <Col sm={8}>
            <Dropdown
              id="zoom-select"
              title="__replace__ %"
              list={this.constant.zooms}
              itemKey="zooms"
              selectedKey="zoom"
              selectedValue={this.state["zoom"]}
              toggleItem={this.toggleSelected}
            />
          </Col>
        </FormGroup>
      </Form>
    );
  }
}

export default class SpectrogramControlButton extends React.Component {
  constructor(props, context) {
    super(props, context);

    this.handleShow = this.handleShow.bind(this);
    this.handleClose = this.handleClose.bind(this);
    this.handleSuccess = this.handleSuccess.bind(this);
    this.nChannels = props.nChannels;
    this.spectViz = props.spectViz;
    this.colourMap = props.colourMap;
    this.zoom = props.zoom;

    this.state = {
      show: false,
    };
  }

  handleClose() {
    this.setState({ show: false });
  }

  handleShow() {
    this.setState({ show: true });
  }

  handleSuccess(row) {
    this.setState({ show: false });
  }

  handleFailure(errorMessage) {
    this.setState({ show: false });
    console.log(errorMessage);
  }

  render() {
    return (
      <React.Fragment>
        <button
          id="spectrogram-control-btn"
          type="button"
          className="btn btn-xs btn-default btn-block"
          onClick={this.handleShow}
        >
          Spectrogram Control
        </button>

        <Modal show={this.state.show} onHide={this.handleClose}>
          <Modal.Header closeButton>
            <Modal.Title>Set spectrogram parameters...</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <SpectrogramControlForm
              onSuccess={this.handleSuccess}
              onFailure={this.handleFailure}
              nChannels={this.nChannels}
              spectViz={this.spectViz}
              zoom={this.zoom}
              colourMap={this.colourMap}
            />
          </Modal.Body>
          <Modal.Footer>
            <div
              className="btn-group btn-group-justified"
              role="group"
              aria-label="group button"
            >
              <div className="btn-group" role="group">
                <button
                  type="submit"
                  id="dialog-modal-yes-button"
                  className="btn btn-primary btn-hover-green"
                  role="button"
                  form="spectrogramControlForm"
                >
                  Confirm
                </button>
              </div>

              <div className="btn-group" role="group">
                <button
                  type="button"
                  id="dialog-modal-no-button"
                  className="btn btn-primary"
                  onClick={this.handleClose}
                >
                  Cancel
                </button>
              </div>
            </div>
          </Modal.Footer>
        </Modal>
      </React.Fragment>
    );
  }
}
