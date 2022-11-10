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
document.querySelector("#contact-form").addEventListener("submit", validateForm);

function validateForm(e) {
  e.preventDefault();

  //   Get input Values
  let name = document.querySelector(".name").value;
  let email = document.querySelector(".email").value;
  let message = document.querySelector(".message").value;
    
  if (name == "" || email == "" || message == "") {
    alert("Must be filled out");
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

// function validateForm() {
//   let x = document.forms["myForm"]["name"].value;
//   let y = document.forms["myForm"]["email"].value;
//   let z = document.forms["myForm"]["message"].value;


//   if (x == "" || y == "" || z == "") {
//     alert("Must be filled out");
//     return false;
//   }
// }

$(function(){
    $("#Areas_of_research_1").on("click",function(){
        window.location = "areas_of_research.html#Areas_research_11";
    });
});

$(function(){
    $("#Areas_of_research_2").on("click",function(){
        window.location = "areas_of_research.html#Areas_research_22";
    });
});
$(function(){
    $("#Areas_of_research_3").on("click",function(){
        window.location = "areas_of_research.html#Areas_research_33";
    });
});
$(function(){
    $("#Areas_of_research_4").on("click",function(){
        window.location = "areas_of_research.html#Areas_research_44";
    });
});




/////////////////////////////////////////////////
$(function(){
    $("#home_1").on("click",function(){
        window.location = "index.html#home_11";
    });
});
$(function(){
    $("#home_2").on("click",function(){
        window.location = "index.html#home_22";
    });
});
$(function(){
    $("#home_3").on("click",function(){
        window.location = "index.html#home_33";
    });
});
$(function(){
    $("#home_4").on("click",function(){
        window.location = "index.html#home_44";
    });
});
////////////////////////////////////////////////////////////////
$(function(){
    $("#empowerment_1").on("click",function(){
        window.location = "empowerment.html#empowerment_11";
    });
});

$(function(){
    $("#empowerment_2").on("click",function(){
        window.location = "empowerment.html#empowerment_22";
    });
});
$(function(){
    $("#empowerment_3").on("click",function(){
        window.location = "empowerment.html#empowerment_33";
    });
});
$(function(){
    $("#empowerment_4").on("click",function(){
        window.location = "empowerment.html#empowerment_44";
    });
});

