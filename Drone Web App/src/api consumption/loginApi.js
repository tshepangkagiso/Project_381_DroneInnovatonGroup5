document.getElementById('loginForm').addEventListener('submit', async function(event) {
    event.preventDefault(); 

    const email = this.email.value;
    const password = this.password.value;

    // Validate input fields
    if (!email || !password) {
        alert('Email and password are required.');
        return;
    }

    try {
        const response = await fetch('http://localhost:3000/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
            credentials: 'include' // This tells the browser to include cookies in the request
        });

        if (response.ok) {
            window.location.href = 'http://localhost:3000/dashboard'; 
        } else {
            const errorText = await response.text();
            alert(`Error: ${errorText}`); 
        }
    } catch (error) {
        console.error('Error during login:', error);
        alert('There was an error processing your request. Please try again later.');
    }
});



async function fetchProtectedData() {
    try {
        const response = await fetch('http://localhost:3000/dashboard', {
            method: 'GET',
            credentials: 'include' // Include cookies in the request
        });

        if (response.ok) {
            const data = await response.json();
            console.log("Protected data:", data);
        } else {
            const errorText = await response.text();
            alert(`Error: ${errorText}`); 
        }
    } catch (error) {
        console.error('Error fetching protected data:', error);
        alert('There was an error accessing the protected resource. Please try again later.');
    }
}


function logout() {
    fetch('http://localhost:3000/logout', {
        method: 'POST',
        credentials: 'include' // Include the cookie in the logout request
    })
    .then(() => {
        window.location.href = 'http://localhost:3000/login'; // Redirect to login page
    })
    .catch(error => {
        console.error('Error during logout:', error);
        alert('There was an error logging out. Please try again later.');
    });
}

