document.getElementById('registerForm').addEventListener('submit', async function (event) {
    event.preventDefault(); 

    const name = this.registerName.value;
    const email = this.registerEmail.value;
    const password = this.registerPassword.value;
    const termsAccepted = this.registerCheck.checked;

    if (!name || !email || !password) {
        alert('Please fill in all fields.');
        return;
    }

    if (!termsAccepted) {
        alert('You must accept the terms and conditions.');
        return;
    }

    const formData = {
        name: name,
        email: email,
        password: password
    };

    try {
        const response = await fetch("http://localhost:3000/create", {
            method: 'POST', 
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData) 
        });

        
        if (response.ok) {
            window.location.href = "http://localhost:3000/login";
        } else {
            const errorText = await response.text();
            alert(`Error: ${errorText}`);
        }
    } catch (error) {
        console.error('Error during registration:', error);
        alert('There was an error processing your request. Please try again later.');
    }
});
