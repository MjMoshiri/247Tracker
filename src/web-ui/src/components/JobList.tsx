import React, { useEffect, useState, useRef, useCallback } from 'react';
import { fetchJobs, fetchCount } from '../services/apiService';
import { JobAd } from '../types/JobAd';
import JobCard from './JobCard';

const JobList: React.FC = () => {
    const [jobs, setJobs] = useState<JobAd[]>([]);
    const [loading, setLoading] = useState(false);
    const [page, setPage] = useState(1);
    const [count, setCount] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const effectRan = useRef(false);

    const handleRemoveJob = useCallback((jobId: string) => {
        setJobs(currentJobs => currentJobs.filter(job => job.id !== jobId));
    }, []);

    const loadJobs = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await fetchJobs(page, 20);
            setJobs(currentJobs => [...currentJobs, ...data]);
        } catch (err) {
            console.error('Failed to load jobs', err);
            setError('Failed to load jobs.');
        } finally {
            setLoading(false);
        }
    }, [page]);

    useEffect(() => {
        if (!effectRan.current) {
            loadJobs();
            effectRan.current = true;
        }
    }, [loadJobs]);

    useEffect(() => {
        const loadCount = async () => {
            try {
                const data = await fetchCount();
                setCount(Math.ceil(data / 20));
            } catch (err) {
                console.error('Failed to load job count', err);
                setError('Failed to load job count.');
            }
        };
        loadCount();
    }, []);

    if (error) return <p style={{ textAlign: 'center', color: 'red' }}>{error}</p>;
    if (loading && jobs.length === 0) return <p>Loading...</p>;
    if (jobs.length === 0) return <p style={{ textAlign: 'center' }}>No jobs found</p>;

    return (
        <div>
            {jobs.map(job => (
                <JobCard key={job.id} job={job} onRemove={handleRemoveJob} />
            ))}
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', margin: '20px 0' }}>
                <button onClick={() => setPage(old => Math.max(old - 1, 1))} disabled={page === 1}>
                    Previous
                </button>
                <span style={{ margin: '0 10px' }}>Page: {page} / {count}</span>
                <button onClick={() => setPage(old => (page < count ? old + 1 : old))} disabled={page >= count}>
                    Next
                </button>
            </div>
            {loading && <p>Loading more jobs...</p>}
        </div>
    );
};

export default JobList;