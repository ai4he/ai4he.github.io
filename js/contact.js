
// Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.13.0/firebase-app.js";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
const firebaseConfig = {
apiKey: "AIzaSyDnJtRzH8A9oShfneVufo_w_m0W8zvy5UM",
authDomain: "haie-68cc6.firebaseapp.com",
projectId: "haie-68cc6",
storageBucket: "haie-68cc6.appspot.com",
messagingSenderId: "309164652738",
appId: "1:309164652738:web:37d9c3aa467678e969e35b"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);


let contactInfo = firebase.database().ref("infos");



document.querySelector("#contact-form").addEventListener("submit",submitForm);

function submitForm(e){
    e.preventDefault();
    
    let name= document.querySelector(".name").value;
    let email= document.querySelector(".email").value;
    let message= document.querySelector(".message").value;
    
    saveContactInfo(name,email,message);
    console.log(name,email,message);



}

function saveContactInfo(name,email,message){
    let newContactInfo = contactInfo.push();
    
    newContactInfo.set({
    
        name = name,
        email = email,
        message = message,
    
    });


}




















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
