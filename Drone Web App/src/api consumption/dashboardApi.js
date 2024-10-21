function logout() {
    fetch('http://localhost:3000/logout', {
        method: 'POST',
        credentials: 'include' // Include cookies in the request
    })
    .then(response => {
        if (response.ok) {
            window.location.href = 'http://localhost:3000/login'; // Redirect to login page
        } else {
            alert('Logout failed, please try again.');
        }
    })
    .catch(error => {
        console.error('Error during logout:', error);
        alert('An error occurred while logging out. Please try again later.');
    });
}

