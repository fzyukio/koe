
require('bootstrap-slider/dist/bootstrap-slider.js');

import React from 'react';
import {Modal} from 'react-bootstrap';
const md5 = require('md5');

import { useState, useEffect } from "react";


class KoeMessage extends React.Component {
    constructor(props) {
        super(props);
        this.message = props.message;
        this.avatar = props.avatar;
    }

    render() {
        return (
            <li className="right clearfix">
                <span className="chat-img pull-right">
                    <img src={this.avatar} alt="Koe Avatar" className="img-circle" />
                </span>
                <div className="chat-body clearfix">
                    <div className="header">
                        <small className=" text-muted"><span className="glyphicon glyphicon-time"></span>13 mins ago</small>
                        <strong className="pull-right primary-font">Koe</strong>
                    </div>
                    <p>{this.message}</p>
                </div>
            </li>
        )
    }
}


class UserMessage extends React.Component {
    constructor(props) {
        super(props);
        this.message = props.message;
        this.name = props.name;
        this.avatar = props.avatar;
    }

    render() {
        return (
            <li className="left clearfix"><span className="chat-img pull-left">
                <img src={this.avatar} alt="User Avatar" className="img-circle" />
            </span>
                <div className="chat-body clearfix">
                    <div className="header">
                        <strong className="primary-font">{this.name}</strong> <small className="pull-right text-muted">
                        <span className="glyphicon glyphicon-time"></span>12 mins ago</small>
                    </div>
                    <p>{this.message}</p>
                </div>
            </li>
        )
    }
}

const KOE = 1;
const USER = 2;


class ChatHistory extends React.Component {
    constructor(props) {
        super(props);
        this.handleSubmit = this.handleSubmit.bind(this);
        this.handleSuccess = props.onSuccess;
        this.handleFailure = props.onFailure;
        this.userName = props.userName;
        this.email = props.email;
        this.koeAvatar = props.koeAvatar;
        
        let hash = md5(this.email.trim().toLowerCase());
        let gravatar = `//www.gravatar.com/avatar/${hash}?s=56`;
        this.userAvatar = gravatar;

        let historyList = localStorage.getItem("chatHistory");
        if (historyList === null) {
            historyList = [
                {
                    "from": KOE,
                    "msg": "Hi there, how can I help you today?"
                },
                {
                    "from": KOE,
                    "msg": "Hi there, how can I help you today?"
                }
            ]
        } else {
            historyList = JSON.parse(historyList)
        }

    }

    handleSubmit(e) {

    }

    componentDidMount() {

    }

    render() {
        return (
            <ul className="chat">
                <KoeMessage 
                    message={"Hi, what can I help you today?"} 
                    avatar={this.koeAvatar}
                />
                <UserMessage 
                    message={"Lorem ipsum dolor sit amet, consectetur adipiscing elit. Curabitur bibendum ornare dolor, quis ullamcorper ligula sodales."} 
                    avatar={this.userAvatar}
                    name={this.userName}
                />
            </ul>
        );

    }
}


export default class ChatButton extends React.Component {
    constructor(props, context) {
        super(props, context);

        this.handleShow = this.handleShow.bind(this);
        this.handleClose = this.handleClose.bind(this);
        this.handleSuccess = this.handleSuccess.bind(this);
        this.userName = props.userName;
        this.email = props.email;
        this.koeAvatar = props.koeAvatar;

        this.state = {
            show: false
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
            <a href="#" onClick={this.handleShow}>
                <span>Ask KoeAI <i className="fa fa-comment chat-open-icon"></i></span>

                <Modal show={this.state.show} onHide={this.handleClose} id="chat-modal">
                    <Modal.Header closeButton>
                        <Modal.Title>Conversation with KoeAI</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <div className="message-box" id="messageBox">
                            <div className="chat-history">
                                <ChatHistory 
                                    userName={this.userName}
                                    email={this.email}
                                    koeAvatar={this.koeAvatar}
                                />
                            </div>
                        </div>
                    </Modal.Body>
                    <Modal.Footer>
                        <button className="btn btn-primary" id="send-message"><i className="fa fa-arrow-up"></i></button>
                        <textarea name="chat-message" id="chat-message"></textarea>
                    </Modal.Footer>
                </Modal>
            </a >
        );
    }
}
