use backend::{Backend, Board};
use futures::channel::oneshot;
use glib::clone;
use gtk::prelude::*;
use std::{cell::RefCell, rc::Rc};

async fn backend_boards() -> (Backend, Vec<Board>) {
    let backend = Backend::new().expect("Failed to create server");

    let boards = Rc::new(RefCell::new(Vec::new()));
    let id1 = backend.connect_board_added(clone!(@strong boards => move |board| {
        boards.borrow_mut().push(board.clone());
    }));

    let (sender, receiver) = oneshot::channel::<()>();
    let sender = RefCell::new(Some(sender));
    let id2 = backend.connect_board_loading_done(move || {
        if let Some(sender) = sender.borrow_mut().take() {
            sender.send(()).unwrap();
        }
    });
    backend.refresh();
    receiver.await.unwrap();

    backend.disconnect(id1);
    backend.disconnect(id2);

    (backend, boards.take())
}

async fn save(usb: bool) {
    let (backend, boards) = backend_boards().await;

    for board in boards {}
}

pub async fn list_boards() {
    let (_backend, boards) = backend_boards().await;

    for board in boards {
        println!("{}", board.model());
    }
}
