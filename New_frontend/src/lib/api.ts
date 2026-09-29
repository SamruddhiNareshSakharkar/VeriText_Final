const API_BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('veritext_token');
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const url = `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorDetail = 'An unexpected error occurred';
    let errData = null;
    try {
      errData = await res.json();
      if (errData && errData.detail) {
        errorDetail = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
      }
    } catch {
      errorDetail = res.statusText || errorDetail;
    }

    if (res.status === 401) {
      localStorage.removeItem('veritext_token');
      localStorage.removeItem('veritext_user');
      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/signup')) {
        window.location.href = '/login';
      }
    }

    throw new ApiError(res.status, errorDetail, errData);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}

// ==========================================
// API METHODS
// ==========================================

export const api = {
  // Auth
  auth: {
    login: (data: any) =>
      apiRequest<{ access_token: string; token_type: string; user: any }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    register: (data: any) =>
      apiRequest<{ access_token: string; token_type: string; user: any }>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    me: () => apiRequest<any>('/auth/me'),
    requestPasswordReset: (email: string) =>
      apiRequest('/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      }),
    confirmPasswordReset: (data: any) =>
      apiRequest('/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  // Teams
  teams: {
    list: () => apiRequest<any[]>('/teams'),
    get: (id: string) => apiRequest<any>(`/teams/${id}`),
    create: (data: { name: string; description?: string; course_code?: string }) =>
      apiRequest<any>('/teams', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (id: string, data: any) =>
      apiRequest<any>(`/teams/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      apiRequest<void>(`/teams/${id}`, {
        method: 'DELETE',
      }),
    join: (join_code: string) =>
      apiRequest<any>('/teams/join', {
        method: 'POST',
        body: JSON.stringify({ join_code }),
      }),
    getMembers: (id: string) => apiRequest<any[]>(`/teams/${id}/members`),
    removeMember: (teamId: string, memberId: string) =>
      apiRequest<void>(`/teams/${teamId}/members/${memberId}`, {
        method: 'DELETE',
      }),
  },

  // Assignments
  assignments: {
    list: () => apiRequest<any[]>('/assignments'),
    listByTeam: (teamId: string) => apiRequest<any[]>(`/teams/${teamId}/assignments`),
    get: (id: string) => apiRequest<any>(`/assignments/${id}`),
    create: (teamId: string, data: any) =>
      apiRequest<any>(`/teams/${teamId}/assignments`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (id: string, data: any) =>
      apiRequest<any>(`/assignments/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      apiRequest<void>(`/assignments/${id}`, {
        method: 'DELETE',
      }),
    uploadSubmission: (assignmentId: string, file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return apiRequest<any>(`/assignments/${assignmentId}/submissions`, {
        method: 'POST',
        body: formData,
      });
    },
    getSubmissions: (assignmentId: string) =>
      apiRequest<any[]>(`/assignments/${assignmentId}/submissions`),
    processAll: (assignmentId: string) =>
      apiRequest<any>(`/assignments/${assignmentId}/process-all`, {
        method: 'POST',
      }),
  },

  // Submissions
  submissions: {
    get: (id: string) => apiRequest<any>(`/submissions/${id}`),
    mySubmissions: () => apiRequest<any[]>('/submissions/me'),
    getAnalysis: (id: string) => apiRequest<any>(`/submissions/${id}/analysis`),
  },

  // Comparison
  comparison: {
    compare: (submission_a_id: string, submission_b_id: string) =>
      apiRequest<any>('/comparison', {
        method: 'POST',
        body: JSON.stringify({ submission_a_id, submission_b_id }),
      }),
    uploadCompare: (fileA: File, fileB: File) => {
      const formData = new FormData();
      formData.append('file_a', fileA);
      formData.append('file_b', fileB);
      return apiRequest<any>('/comparison/upload-compare', {
        method: 'POST',
        body: formData,
      });
    },
  },

  // Grading
  grading: {
    getConfig: (assignmentId: string) =>
      apiRequest<any>(`/assignments/${assignmentId}/grading-config`),
    saveConfig: (assignmentId: string, data: any) =>
      apiRequest<any>(`/assignments/${assignmentId}/grading-config`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getGrade: (submissionId: string) =>
      apiRequest<any>(`/submissions/${submissionId}/grade`),
    submitGrade: (submissionId: string, data: any) =>
      apiRequest<any>(`/submissions/${submissionId}/grade`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    myGrades: () => apiRequest<any[]>('/grades/me'),
  },

  // Reports
  reports: {
    list: (assignmentId: string) =>
      apiRequest<any[]>(`/assignments/${assignmentId}/reports`),
    generate: (assignmentId: string, data: { report_type?: string; title?: string }) =>
      apiRequest<any>(`/assignments/${assignmentId}/reports`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    downloadUrl: (reportId: string) => `${API_BASE}/reports/${reportId}/download`,
  },

  // Analytics
  analytics: {
    stats: () => apiRequest<any>('/dashboard/stats'),
    teacherDashboard: () => apiRequest<any>('/dashboard/stats'),
    studentDashboard: () => apiRequest<any>('/dashboard/stats'),
    cohort: (assignmentId: string) =>
      apiRequest<any>(`/assignments/${assignmentId}/cohort-analytics`),
  },

  // Audit
  audit: {
    list: (limit = 100, offset = 0) =>
      apiRequest<any[]>(`/audit?limit=${limit}&offset=${offset}`),
  },
};
