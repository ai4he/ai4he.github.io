const firebaseConfig = {
    apiKey: "AIzaSyBOCyN-cIeyooxE0-6PEaEU2QCiwq2aNZU",
    authDomain: "haie-3ca3b.firebaseapp.com",
    databaseURL: "https://haie-3ca3b-default-rtdb.firebaseio.com",
    projectId: "haie-3ca3b",
    storageBucket: "haie-3ca3b.appspot.com",
    messagingSenderId: "247177631427",
    appId: "1:247177631427:web:871240f70e29212f0eb476"
  };

firebase.initializeApp(firebaseConfig);

// Refernece contactInfo collections
let contactInfo = firebase.database().ref("HAIE");

// Listen for a submit
document.querySelector("#contact-form").addEventListener("submit", submitForm);

function submitForm(e) {
  e.preventDefault();

  //   Get input Values
  let name = document.querySelector(".name").value;
  let email = document.querySelector(".email").value;
  let message = document.querySelector(".message").value;
  console.log(name, email, message);
    
  if(name == "" or email=="" or message="") {
        alert("Plese fill the areas");
        return false;
    }

  saveContactInfo(name, email, message);
    
  msgSent();

  document.querySelector("#contact-form").reset();
}

// Save infos to Firebase
function saveContactInfo(name, email, message) {
  let newContactInfo = contactInfo.push();

  newContactInfo.set({
    name: name,
    email: email,
    message: message,
  });
}
function msgSent() {
    document.getElementById('msgSent').innerHTML = 'Message Sent Successfully';
}
