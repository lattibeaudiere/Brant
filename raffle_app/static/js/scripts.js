function startCountdown(endTime, elementId) {
    const targetDate = new Date(endTime).getTime();
    const countdownElement = document.getElementById(elementId);

    if (!countdownElement) {
        console.error("Countdown element not found: " + elementId);
        return;
    }
    if (isNaN(targetDate)) {
        console.error("Invalid endTime for element: " + elementId, endTime);
        countdownElement.innerHTML = "Invalid end time";
        return;
    }

    const interval = setInterval(function() {
        const now = new Date().getTime();
        const distance = targetDate - now;

        // Time calculations for days, hours, minutes and seconds
        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);

        // Output the result in an element with id="countdown_X"
        if (distance < 0) {
            clearInterval(interval);
            countdownElement.innerHTML = "EXPIRED";
            // Optionally, refresh the part of the page or redirect
        } else {
            countdownElement.innerHTML = days + "d " + hours + "h "
            + minutes + "m " + seconds + "s ";
        }
    }, 1000);
}
