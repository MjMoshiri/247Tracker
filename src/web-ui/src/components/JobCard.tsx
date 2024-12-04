import React, { useState, useRef, useCallback } from 'react';
import { JobAd } from '../types/JobAd';
import { updateJob } from '../services/apiService';
import '../css/JobCard.css';

interface JobCardProps {
    job: JobAd;
    onRemove: (jobId: string) => void;
}

const JobCard: React.FC<JobCardProps> = ({ job: Ad, onRemove }) => {
    const [isCollapsed, setIsCollapsed] = useState(true);
    const [isProcessing, setIsProcessing] = useState(false);
    const accordionTitleRef = useRef<HTMLHeadingElement>(null);

    const handleUpdateJob = useCallback(async (status: 'applied' | 'declined') => {
        setIsProcessing(true);
        try {
            const updatedJob = {
                ...Ad,
                is_qualified: status === 'applied',
                processed: true,
                date_processed: Math.floor(Date.now() / 1000)
            };
            await updateJob(updatedJob);
            toggleCollapse();
            onRemove(Ad.id);
        } catch (error) {
            console.error('Failed to update job:', error);
        } finally {
            setIsProcessing(false);
        }
    }, [Ad, onRemove]);

    const toggleCollapse = useCallback(() => {
        accordionTitleRef.current?.classList.toggle('collapsed');
        setIsCollapsed(prev => !prev);
    }, []);

    return (
        <div className="ad-container">
            <h2
                ref={accordionTitleRef}
                className="ad-title accordion-title"
                onClick={toggleCollapse}
                aria-expanded={!isCollapsed}
                role="button"
                tabIndex={0}
                onKeyPress={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        toggleCollapse();
                    }
                }}
            >
                {Ad.title}, {Ad.company}
            </h2>
            {!isCollapsed && (
                <>
                    <p className="ad-date">Added on: {new Date(Ad.date_added * 1000).toLocaleDateString()}</p>
                    <a className="ad-link" href={Ad.link} target="_blank" rel="noreferrer">Link to job</a>
                    <br />
                    <button
                        className="applied-button"
                        onClick={() => handleUpdateJob('applied')}
                        disabled={isProcessing}
                    >
                        Applied
                    </button>
                    <button
                        className="declined-button"
                        onClick={() => handleUpdateJob('declined')}
                        disabled={isProcessing}
                    >
                        Declined
                    </button>
                    <p className="ad-description">{Ad.description}</p>
                </>
            )}
        </div>
    );
};

export default JobCard;