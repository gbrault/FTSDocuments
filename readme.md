# FTSDOCUMENTS

## Description

**THIS IS A WORK IN PROGRESS**

This project is a mockup of a document library with full text search capabilities.
This project is complementing Daniel Vaz Gaspar example of flask-Appbuilder. You can find the original project [here](https://github.com/dpgaspar/Flask-AppBuilder/tree/master/examples/quickfiles).
The "project" concept being replaced by "Documents".

This app enables you to upload and manage documents. It is a simple app that can be used as a starting point for your own app.

I have added a few features to the original project:

- The original project enables to create "Projects" and within a "Project", you can upload/donwload documents.
- I have replaced the "Project" concept by "Documents". You can upload documents and manage them. This is a kind of Document Library.
- Document Files is the list of documents, including a description and a file. They are attached To a Document Library.
- The real new feature is that each time a document is uploaded in the library, a Full Text Search index is created.
- I have added a search view in the document library using the search box. The search is based on the Full Text Search index if you use the Match capability.
- The Match capability is added for Text and Strings columns. It is based on the [FTS5](https://www.sqlite.org/fts5.html) extension of SQLite.
- I have also improved the redering, has all the words in the match search request are highlighted in the document.

To do that, I have changed few things in the flask-appbuilder project:

You need to use https://github.com/seadevfr/Flask-AppBuilder.git to install the appropriate version of flask-appbuilder.

## Installation

Have a look at the requirements.txt file to see the list of dependencies.

Outline the steps required to install the application.

- best is to use Visual Studio Code
- git clone this repository
- create a virtualenv
- install the dependencies
- use the "Python: Flask" option to run the app
- the login page should show up

![](images/login.png)

## Usage

A default user is created (ad min): user: admin, password: password

- Input the credentials

![](images/credentials.png)

- The main page should show up

![](images/main.png)

- Click on the "Document" menu

![](images/Documents.png)

- Click on the Documents menu

![](images/documentview.png)

- Click on the "Show" button (a magnifying glass) to see the document library

![](images/documentlibrary.png)

- Should you click on a download link, you will view the document as a new tab in the browser

![](images/book.png)

## Configuration


## Contributing


## Credits


## License


## Changelog


