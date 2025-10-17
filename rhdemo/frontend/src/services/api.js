import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
});

export function getEmployes() {
  return api.get('/employes');
}

export function getEmploye(id) {
  return api.get('/employe', { params: { id } });
}

export function saveEmploye(employe) {
  console.log('Données envoyées au backend:', employe);
  return api.post('/employe', employe);
}

export function testSaveEmploye(employe) {
  console.log('TEST - Données envoyées au backend:', employe);
  return api.post('/test-employe', employe);
}

export function deleteEmploye(id) {
  return api.delete('/employe', { params: { id } });
}