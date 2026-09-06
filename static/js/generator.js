const generatorForm = document.getElementById('generatorForm');
const generateButton = document.getElementById('generateBtn');
const statusMessage = document.getElementById('statusMessage');
const resultContainer = document.getElementById('resultContainer');
const downloadLink = document.getElementById('downloadLink');
const previewContainer = document.getElementById('previewContainer');

async function handleGenerate() {
    if (!generatorForm) {
        return;
    }

    resultContainer.style.display = 'none';
    statusMessage.textContent = '';

    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    const formData = new FormData(generatorForm);
    const payload = {};
    formData.forEach((value, key) => {
        payload[key] = value;
    });

    try {
        statusMessage.textContent = 'Generating document...';
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });

        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }

        const result = await response.json();
        if (response.status === 403) {
            window.location.href = '/kyc?msg=' + encodeURIComponent(result.msg || 'Please complete KYC verification before proceeding.');
            return;
        }
        if (!response.ok) {
            statusMessage.textContent = result.msg || 'Document generation failed. Please try again.';
            return;
        }

        downloadLink.href = result.download_url || '#';
        downloadLink.textContent = result.download_url ? 'Download generated DOCX' : 'Download link unavailable';
        previewContainer.innerHTML = result.preview_html || '<p>No preview available.</p>';
        resultContainer.style.display = 'block';
        statusMessage.textContent = 'Loan agreement generated successfully.';
    } catch (error) {
        statusMessage.textContent = 'Unable to connect to the server. Please try again.';
        console.error(error);
    }
}

if (generateButton) {
    generateButton.addEventListener('click', handleGenerate);
}
