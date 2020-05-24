require('bootstrap-slider/dist/bootstrap-slider.js');

import React from 'react';
import {getUrl, deepCopy} from "../utils";
import ReactDOM from 'react-dom';
import {
    Modal,
    Form,
    Col,
    FormControl,
    FormGroup,
    ButtonToolbar,
    DropdownButton,
    MenuItem,
    MenuItemLink
} from 'react-bootstrap';
import {LinkContainer} from 'react-router-bootstrap'

import $ from 'jquery';
//
//
// class Slider extends React.Component {
//     componentDidMount() {
//         var $this = $(ReactDOM.findDOMNode(this));
//         console.log($this);
//         $this.find("input").slider();
//     }
//
//     render() {
//         return (
//             <div className="control-item slider-group row no-margin">
//                 <div className="col-xs-2 no-padding slider-label">FFT Window</div>
//                 <div className="col-xs-10 no-padding-left">
//                     <input id="slider" type="text"
//                            data-provide="slider"
//                            data-slider-ticks="[1, 2, 3, 4]"
//                            data-slider-ticks-labels='["128", "256", "512", "1024"]'
//                            data-slider-min="1"
//                            data-slider-max="3"
//                            data-slider-step="1"
//                            data-slider-value="3"
//                            data-slider-tooltip="hide"/>
//                 </div>
//             </div>
//         );
//     }
// }


class Dropdown extends React.Component {
    static getDerivedStateFromProps(nextProps) {
        return {headerTitle: nextProps.title.replace("__replace__", nextProps.selectedValue)};
    }

    constructor(props) {
        super(props);
        this.toggleItem = props.toggleItem;
        this.itemKey = props.itemKey;
        this.selectedKey = props.selectedKey;
        this.handleChange = props.onChange;

        this.state = {
            listOpen: false,
            headerTitle: props.title,
        }
    }

    render() {
        const {list, selectedValue} = this.props;
        const {listOpen, headerTitle} = this.state;
        return (
            <DropdownButton bsStyle="default" title={headerTitle} id={this.props.id}>
                {list.map((item) => (
                    <MenuItem className={item === selectedValue ? "active" : ""} key={item} onClick={() => this.toggleItem(item, this.itemKey, this.selectedKey)}>
                        {item}
                    </MenuItem>
                ))}
            </DropdownButton>
        )
    }
}

class NewDatabaseForm extends React.Component {
    toggleSelected(selectedItem, itemKey, selectedKey) {
        let list = this.state[itemKey];
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
        this.constant = {
            fftValues: [128, 256, 512, 1024],
            overlaps: [25, 50, 75],
        };

        this.state = {
            'new-database-fft': 512,
            'new-database-overlap': 50,
            'new-database-name': '',
            'new-database-hpf': 0,
            'new-database-lpf': '',

            'new-database-name-error': '',
            'new-database-lpf-error': ''
        };

        this.originalState = deepCopy(this.state);
    }

    handleSubmit(e) {
        e.preventDefault();
        let $self = $(ReactDOM.findDOMNode(this));
        let self = this;
        let state = self.state;

        let url = getUrl('send-request', 'koe/create-database');
        console.log(state);

        $.post(url, state).done(function (response) {
            response = JSON.parse(response);

            if (response.success) {
                let row = response.payload;
                let errors = {
                    'new-database-name-error': '',
                    'new-database-lpf-error': ''
                };
                self.setState(self.originalState);
                self.handleSuccess(row);
            } else {
                let errors = response.payload;
                self.setState(errors);
            }

        }).fail(function (response) {
            let errorMessage = JSON.parse(response.responseText);
            self.handleFailure(errorMessage);
        });

    }

    render() {
        let nameError = this.state['new-database-name-error'];
        let lpfError = this.state['new-database-lpf-error'];

        return (
            <Form horizontal onSubmit={this.handleSubmit} id="newDatabaseForm">
                <FormGroup>
                    <Col sm={4}>
                        Name
                    </Col>
                    <Col sm={8}>
                        <FormControl className={nameError ? "has-error" : ""} type="text" placeholder="Name"
                                     id="new-database-name" onChange={this.handleFieldChange}/>
                        <ul className="errorlist"><li>{nameError}</li></ul>
                    </Col>
                </FormGroup>

                <FormGroup>
                    <Col sm={4}>
                        FFT Window
                    </Col>
                    <Col sm={8}>
                        <Dropdown
                            id="nfft-select"
                            title="__replace__ samples"
                            list={this.constant.fftValues}
                            itemKey="fftValues" selectedKey="new-database-fft"
                            selectedValue={this.state['new-database-fft']}
                            toggleItem={this.toggleSelected}
                        />

                    </Col>
                </FormGroup>

                <FormGroup>
                    <Col sm={4}>
                        Overlap
                    </Col>
                    <Col sm={8}>
                        <Dropdown
                            id="overlap-select"
                            title="Overlap between two consecutive windows: __replace__ %"
                            list={this.constant.overlaps}
                            itemKey="overlaps" selectedKey="new-database-overlap"
                            selectedValue={this.state['new-database-overlap']}
                            toggleItem={this.toggleSelected}
                        />

                    </Col>
                </FormGroup>

                <FormGroup>
                    <Col sm={4}>
                        High pass filter
                    </Col>
                    <Col sm={8}>
                        <FormControl type="number" placeholder="E.g. 100Hz, default is 0 (no filter)"
                                     value={this.state['new-database-hpf']}
                                     id="new-database-hpf" onChange={this.handleFieldChange}/>
                    </Col>
                </FormGroup>

                <FormGroup>
                    <Col sm={4}>
                        Low pass filter
                    </Col>
                    <Col sm={8}>
                        <FormControl className={lpfError ? "has-error" : ""} type="number"
                                     placeholder="E.g. 10000Hz, default is no filter"
                                     id="new-database-lpf" onChange={this.handleFieldChange}/>
                        <ul className="errorlist"><li>{lpfError}</li></ul>
                    </Col>
                </FormGroup>

            </Form>
        );

    }
}


export default class NewDatabaseButton extends React.Component {
    constructor(props, context) {
        super(props, context);

        this.handleShow = this.handleShow.bind(this);
        this.handleClose = this.handleClose.bind(this);
        this.handleSuccess = this.handleSuccess.bind(this);
        this.databaseGrid = props.databaseGrid;

        this.state = {
            show: false
        };
    }

    handleClose() {
        this.setState({show: false});
    }

    handleShow() {
        this.setState({show: true});
    }

    handleSuccess(row) {
        this.setState({show: false});
        this.databaseGrid.appendRowAndHighlight(row);
    }

    handleFailure(errorMessage) {
        this.setState({show: false});
        console.log(errorMessage);
    }

    render() {
        return (
            <div>
                <button id="create-database-btn" type="button"
                        className="btn btn-sm btn-black"
                        onClick={this.handleShow}>
                    New database
                </button>

                <Modal show={this.state.show} onHide={this.handleClose}>
                    <Modal.Header closeButton>
                        <Modal.Title>Creating a new database...</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <NewDatabaseForm onSuccess={this.handleSuccess} onFailure={this.handleFailure}/>
                    </Modal.Body>
                    <Modal.Footer>
                        <div className="btn-group btn-group-justified" role="group" aria-label="group button">
                            <div className="btn-group" role="group">
                                <button type="submit" id="dialog-modal-yes-button"
                                        className="btn btn-primary btn-hover-green"
                                        role="button" form='newDatabaseForm'>
                                    Confirm
                                </button>
                            </div>

                            <div className="btn-group" role="group">
                                <button type="button" id="dialog-modal-no-button"
                                        className="btn btn-primary" onClick={this.handleClose}>
                                    Cancel
                                </button>
                            </div>
                        </div>
                    </Modal.Footer>
                </Modal>
            </div >
        );
    }
}
